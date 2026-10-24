"""Convert a day with peak memory set by the part size, not the day (Ilia, 2026-10-23).

convert_parts reads the whole day's rows (34 bytes per book row, 6.3 GB on 2024-05-01)
before it cuts parts. This reader streams the CSV three times instead and never holds more
than one part, the rows near each cut target, and a 64 MB CSV chunk:

1. Day statistics: rows, the day's exchange-time span, the most negative feed latency, the
   snapshot blocks, and value counts for the inferred tick and lot.
2. Cut search: for each target, only the rows within the search window, plus the latest
   local time sent before it and the earliest sent after it. The clean-cut rule itself is
   convert._clean_cuts_from, the same code convert_parts uses.
3. Conversion: rows go to their part by exchange time and each part runs through the same
   hftbacktest steps (convert.part_events, convert.order_part).

Pass 3 needs each file's rows to reach the parts in order, which holds when the file
follows local time and the cuts are clean; a row of an earlier part after a later part
has started raises ConversionError. The output equals convert_parts' for the same cuts,
and the concatenated events equal it for any clean cuts (tests/unit/test_stream_convert.py).
"""

import math
from pathlib import Path

import numpy as np
from hftbacktest import DEPTH_SNAPSHOT_EVENT
from numba import njit

from toxic_flow.data.convert import (
    I64,
    ConversionError,
    _clean_cuts_from,
    _csv_chunks,
    _depth_rows,
    _trade_rows,
    depth_schema,
    order_part,
    part_events,
    trade_schema,
)
from toxic_flow.data.validate import DECIMALS, infer_increment

EVENTS_PER_PART = 5_000_000  # a part's working set is about 240 bytes per event
CHUNK_BYTES = 64 << 20


def _chunks(path: Path, kind: str, chunk_bytes: int):
    schema, to_rows = (
        (trade_schema, _trade_rows) if kind == "trades" else (depth_schema, _depth_rows)
    )
    for df in _csv_chunks(Path(path), schema, chunk_bytes):
        yield to_rows(df)


@njit(cache=True)
def _snapshot_scan(exch_ts, side, is_snapshot, state, out):
    """convert._snapshot_blocks over one chunk, carrying an open block across chunks in
    state = (in_block, bid rows, ask rows, first, last). Closed blocks go to out as
    (first, last, closing row's exch_ts, bid rows, ask rows); returns how many."""
    n = 0
    for i in range(len(is_snapshot)):
        if is_snapshot[i] == 1:
            if state[0] == 0:
                state[0], state[1], state[2], state[3], state[4] = 1, 0, 0, exch_ts[i], exch_ts[i]
            state[3] = min(state[3], exch_ts[i])
            state[4] = max(state[4], exch_ts[i])
            if side[i] == 1:
                state[1] += 1
            else:
                state[2] += 1
        elif state[0] == 1:
            state[0] = 0
            out[n, 0], out[n, 1], out[n, 2] = state[3], state[4], exch_ts[i]
            out[n, 3], out[n, 4] = state[1], state[2]
            n += 1
    return n


def _add_counts(acc, values):
    v, c = np.unique(np.round(values, DECIMALS), return_counts=True)
    if acc is None:
        return v, c
    allv, inv = np.unique(np.concatenate([acc[0], v]), return_inverse=True)
    return allv, np.bincount(inv, weights=np.concatenate([acc[1], c])).astype(np.int64)


def _stats(trades_path, depth_path, chunk_bytes):
    """Pass 1."""
    st = {"rows": {}, "dtype": {}, "t_lo": I64.max, "t_hi": I64.min, "min_lat": I64.max}
    counts = {"book_px": None, "trade_px": None, "trade_qty": None}
    blocks, state = [], np.zeros(5, np.int64)
    for kind, path in (("trades", trades_path), ("depth", depth_path)):
        n = 0
        for rows in _chunks(path, kind, chunk_bytes):
            n += len(rows)
            st["dtype"][kind] = rows.dtype
            if not len(rows):
                continue
            st["t_lo"] = min(st["t_lo"], int(rows["exch_ts"].min()))
            st["t_hi"] = max(st["t_hi"], int(rows["exch_ts"].max()))
            st["min_lat"] = min(st["min_lat"], int((rows["local_ts"] - rows["exch_ts"]).min()))
            if kind == "trades":
                counts["trade_px"] = _add_counts(counts["trade_px"], rows["px"])
                counts["trade_qty"] = _add_counts(counts["trade_qty"], rows["qty"])
            else:
                counts["book_px"] = _add_counts(counts["book_px"], rows["px"])
                out = np.empty((int((rows["is_snapshot"] == 0).sum()) + 1, 5), np.int64)
                k = _snapshot_scan(rows["exch_ts"], rows["side"], rows["is_snapshot"], state, out)
                blocks.append(out[:k])
        if n == 0:
            raise ConversionError(f"{path} has a header and no rows")
        st["rows"][kind] = n
    st["blocks"] = np.concatenate(blocks) if blocks else np.empty((0, 5), np.int64)
    st["counts"] = counts
    return st


def _inferred(counts, n_book, n_trades) -> dict:
    """convert.infer_from_rows from value counts instead of rows."""
    tick, book_off = infer_increment(*counts["book_px"])
    lot, qty_off = infer_increment(*counts["trade_qty"])
    v, c = counts["trade_px"]
    off = np.abs(v / tick - np.round(v / tick)) > 1e-6
    return {
        "tick_size": tick,
        "book_rows": n_book,
        "book_rows_off_tick_grid": book_off,
        "trade_rows": n_trades,
        "trade_rows_off_tick_grid": int(c[off].sum()),
        "lot_size": lot,
        "trade_rows_off_lot_grid": qty_off,
    }


def _find_cuts(paths, targets, windows_ns, blocks, chunk_bytes) -> list[int]:
    """Pass 2: convert.find_cuts with each window's rows gathered by streaming."""
    cuts = {}
    todo = list(range(len(targets)))
    for window_ns in windows_ns:
        if not todo:
            break
        lo = {j: targets[j] - window_ns for j in todo}
        hi = {j: targets[j] + window_ns for j in todo}
        before = dict.fromkeys(todo, I64.min)
        after = dict.fromkeys(todo, I64.max)
        rows = {j: ([], []) for j in todo}
        for kind, path in paths:  # trades, then depth, as convert_parts concatenates them
            for chunk in _chunks(path, kind, chunk_bytes):
                e, loc = chunk["exch_ts"], chunk["local_ts"]
                for j in todo:
                    m = e < lo[j]
                    if m.any():
                        before[j] = max(before[j], int(loc[m].max()))
                    m = e >= hi[j]
                    if m.any():
                        after[j] = min(after[j], int(loc[m].min()))
                    m = (e >= lo[j]) & (e < hi[j])
                    if m.any():
                        rows[j][0].append(e[m])
                        rows[j][1].append(loc[m])
        still = []
        for j in todo:
            e_w = np.concatenate(rows[j][0]) if rows[j][0] else np.empty(0, np.int64)
            l_w = np.concatenate(rows[j][1]) if rows[j][1] else np.empty(0, np.int64)
            cand = _clean_cuts_from(e_w, l_w, before[j], after[j], blocks)
            if len(cand):
                cuts[j] = int(cand[np.argmin(np.abs(cand - targets[j]))])
            else:
                still.append(j)
        todo = still
    if todo:
        raise ConversionError(f"no clean cut within {max(windows_ns)} ns of {targets[todo[0]]}")
    return [cuts[j] for j in range(len(targets))]


def _part_rows(path, kind, cuts, n_parts, dtype, chunk_bytes):
    """Pass 3, one file: yield each part's rows in file order, parts 0 to n_parts - 1."""
    last, pieces, k_now = 0, [], 0
    for chunk in _chunks(path, kind, chunk_bytes):
        k = np.searchsorted(cuts, chunk["exch_ts"], side="right")
        if len(k) and (k[0] < last or (np.diff(k) < 0).any()):
            raise ConversionError(
                f"{path}: a row of an earlier part follows a later part in file order"
            )
        if len(k):
            last = int(k[-1])
        for part in np.unique(k):
            while k_now < part:
                yield np.concatenate(pieces) if pieces else np.empty(0, dtype)
                pieces, k_now = [], k_now + 1
            pieces.append(chunk[k == part])
    while k_now < n_parts:
        yield np.concatenate(pieces) if pieces else np.empty(0, dtype)
        pieces, k_now = [], k_now + 1


def convert_parts_streamed(
    trades_path: Path,
    depth_path: Path,
    n_parts: int | None = None,
    events_per_part: int = EVENTS_PER_PART,
    chunk_bytes: int = CHUNK_BYTES,
    search_windows_us: tuple = (300_000_000, 1_800_000_000),
    sink=None,
) -> tuple[list[np.ndarray], dict]:
    """Same contract as convert.convert_parts: (parts, info), or each part to sink(k, part)."""
    paths = (("trades", trades_path), ("depth", depth_path))
    st = _stats(trades_path, depth_path, chunk_bytes)
    n_rows = st["rows"]["trades"] + st["rows"]["depth"]
    if n_parts is None:
        n_parts = max(1, math.ceil(n_rows / events_per_part))
    blk = st["blocks"]
    lo, hi, close, nb, na = (blk[:, i] for i in range(5))
    min_lat = st["min_lat"]
    offset = -min_lat if min_lat < 0 else 0
    targets = [st["t_lo"] + (st["t_hi"] - st["t_lo"]) * k // n_parts for k in range(1, n_parts)]
    windows_ns = tuple(w * 1000 for w in search_windows_us)
    cuts = _find_cuts(
        paths, targets, windows_ns, list(zip(lo, hi, close, strict=True)), chunk_bytes
    )
    if any(b <= a for a, b in zip(cuts, cuts[1:], strict=False)):
        raise ConversionError(f"cuts are not strictly increasing: {cuts}")

    cut_arr = np.asarray(cuts, np.int64)
    gen_t = _part_rows(trades_path, "trades", cut_arr, n_parts, st["dtype"]["trades"], chunk_bytes)
    gen_d = _part_rows(depth_path, "depth", cut_arr, n_parts, st["dtype"]["depth"], chunk_bytes)
    parts, sizes, emitted, prev_max_local = [], [], 0, None
    for k, (t_seg, d_seg) in enumerate(zip(gen_t, gen_d, strict=True)):
        tmp = part_events(t_seg, d_seg, k)
        del t_seg, d_seg
        emitted += int(((tmp["ev"] & 0xFF) == DEPTH_SNAPSHOT_EVENT).sum())
        if prev_max_local is not None and int(tmp["local_ts"].min()) <= prev_max_local:
            raise ConversionError(f"cut {k} is not clean: messages in flight across it")
        prev_max_local = int(tmp["local_ts"].max())
        data = order_part(tmp, offset)
        del tmp
        sizes.append(len(data))
        if sink is None:
            parts.append(data)
        else:
            sink(k, data)
        del data
    if emitted != int(nb.sum() + na.sum()):
        raise ConversionError(
            f"parts emitted {emitted} snapshot rows, the one-shot pass {int(nb.sum() + na.sum())}"
        )
    info = {
        "n_parts": n_parts,
        "cuts": cuts,
        "events_per_part": sizes,
        "trade_rows": st["rows"]["trades"],
        "depth_rows": st["rows"]["depth"],
        "snapshot_blocks": len(lo),
        "snapshot_levels_bid_ask": [[int(b), int(a)] for b, a in zip(nb, na, strict=True)][:10],
        "min_feed_latency_ns": min_lat,
        "local_ts_offset_ns": offset,
        "inferred": _inferred(st["counts"], st["rows"]["depth"], st["rows"]["trades"]),
        "reader": "streamed",
    }
    return parts, info
