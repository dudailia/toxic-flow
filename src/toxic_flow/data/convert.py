"""Convert one day of Tardis CSV into hftbacktest's event format, in parts that fit in memory.

Usage: uv run python -m toxic_flow.data.convert train|val|test|YYYY-MM-DD

hftbacktest's tardis.convert does a whole day in one pass. A BTCUSDT day is about 98M
events (6.3 GB as hftbacktest events) and that pass peaks near 14 GB, more than this
machine has. convert_parts runs the same hftbacktest steps (_convert_depth, the
local-timestamp offset of correct_local_timestamp, correct_event_order,
validate_event_order) but streams the CSV in chunks, keeps only the columns those steps
read, and splits the day at clean cuts: instants B where every message sent before B was
received before every message sent after B. At a clean cut the exchange-time and
local-time orders do not interleave across B, so the parts, concatenated, equal the
one-shot output. tests/unit/test_convert.py checks that against tardis.convert itself.
Anything that would make the parts differ raises ConversionError instead.

A ConversionError is a failure of this splitter, not of hftbacktest, so it is not
exclusion rule 2 of PREREGISTRATION.md section 2. It stops the pipeline for Ilia.
"""

import gzip
import json
import math
import os
import resource
import shutil
import sys
import time
from pathlib import Path

import hftbacktest
import numpy as np
import polars as pl
from hftbacktest import BUY_EVENT, DEPTH_SNAPSHOT_EVENT, SELL_EVENT, TRADE_EVENT
from hftbacktest.data.utils.tardis import _convert_depth, depth_schema, trade_schema
from hftbacktest.data.validation import correct_event_order, validate_event_order
from hftbacktest.types import event_dtype
from numba import njit

from toxic_flow.data.download import (
    MANIFEST,
    RAW,
    ManifestError,
    load_manifest,
    resolve_days,
    sha256_file,
)
from toxic_flow.data.split_lock import SplitLockError, assert_allowed, normalise
from toxic_flow.data.tardis import DATA_TYPES
from toxic_flow.data.validate import infer_from_rows

ROOT = Path(__file__).resolve().parents[3]
CONVERTED = ROOT / "data" / "converted"
SS_BUFFER_SIZE = 1_000_000  # tardis.convert's default ss_buffer_size
I64 = np.iinfo(np.int64)


class ConversionError(RuntimeError):
    pass


def _csv_chunks(path: Path, schema: dict, chunk_bytes: int):
    """Yield DataFrames of whole CSV lines, so the decompressed day is never all in memory."""
    with gzip.open(path, "rb") as f:
        f.readline()  # header; the schema gives the names
        rest = b""
        while True:
            block = f.read(chunk_bytes)
            buf = rest + block
            cut = buf.rfind(b"\n") + 1 if block else len(buf)
            buf, rest = buf[:cut], buf[cut:]
            if buf:
                yield pl.read_csv(buf, has_header=False, schema=schema)
            if not block:
                return


def _count_rows(path: Path, chunk_bytes: int) -> int:
    with gzip.open(path, "rb") as f:
        n = sum(block.count(b"\n") for block in iter(lambda: f.read(chunk_bytes), b""))
    return n - 1  # header line; Tardis files end with a newline


def _read(path: Path, schema: dict, chunk_bytes: int, to_array) -> np.ndarray:
    """Fill one preallocated array chunk by chunk; a list of chunks plus np.concatenate
    would hold the 3.3 GB depth array twice."""
    n = _count_rows(path, chunk_bytes)
    out, pos = None, 0
    for df in _csv_chunks(path, schema, chunk_bytes):
        arr = to_array(df)
        if out is None:
            out = np.empty(n, arr.dtype)
        out[pos : pos + len(arr)] = arr
        pos += len(arr)
    if pos != n:
        raise ConversionError(f"{path}: parsed {pos} rows, counted {n}")
    return out


def read_trades(path: Path, chunk_bytes: int) -> np.ndarray:
    return _read(path, trade_schema, chunk_bytes, _trade_rows)


def read_depth(path: Path, chunk_bytes: int) -> np.ndarray:
    return _read(path, depth_schema, chunk_bytes, _depth_rows)


def _trade_rows(df: pl.DataFrame) -> np.ndarray:
    # Same expressions as hftbacktest/data/utils/tardis.py convert(), trades branch.
    return (
        df.with_columns(
            pl.when(pl.col("side") == "buy")
            .then(BUY_EVENT | TRADE_EVENT)
            .when(pl.col("side") == "sell")
            .then(SELL_EVENT | TRADE_EVENT)
            .otherwise(TRADE_EVENT)
            .cast(pl.UInt64, strict=True)
            .alias("ev"),
            (pl.col("timestamp") * 1000).cast(pl.Int64, strict=True).alias("exch_ts"),
            (pl.col("local_timestamp") * 1000).cast(pl.Int64, strict=True).alias("local_ts"),
            pl.col("price").cast(pl.Float64, strict=True).alias("px"),
            pl.col("amount").cast(pl.Float64, strict=True).alias("qty"),
            pl.lit(0).cast(pl.UInt64, strict=True).alias("order_id"),
            pl.lit(0).cast(pl.Int64, strict=True).alias("ival"),
            pl.lit(0.0).cast(pl.Float64, strict=True).alias("fval"),
        )
        .select(["ev", "exch_ts", "local_ts", "px", "qty", "order_id", "ival", "fval"])
        .to_numpy(structured=True)
    )


def _depth_rows(df: pl.DataFrame) -> np.ndarray:
    # Same expressions as hftbacktest/data/utils/tardis.py convert(), depth branch.
    return (
        df.with_columns(
            (pl.col("timestamp") * 1000).cast(pl.Int64, strict=True).alias("exch_ts"),
            (pl.col("local_timestamp") * 1000).cast(pl.Int64, strict=True).alias("local_ts"),
            pl.col("price").cast(pl.Float64, strict=True).alias("px"),
            pl.col("amount").cast(pl.Float64, strict=True).alias("qty"),
            pl.when((pl.col("side") == "bid") | (pl.col("side") == "buy"))
            .then(1)
            .when((pl.col("side") == "ask") | (pl.col("side") == "sell"))
            .then(-1)
            .otherwise(0)
            .cast(pl.Int8, strict=True)
            .alias("side"),
            pl.when(pl.col("is_snapshot"))
            .then(1)
            .otherwise(0)
            .cast(pl.Int8, strict=True)
            .alias("is_snapshot"),
        )
        .select(["exch_ts", "local_ts", "px", "qty", "side", "is_snapshot"])
        .to_numpy(structured=True)
    )


@njit(cache=True)
def _snapshot_blocks(exch_ts, side, is_snapshot, buffer_size):
    """Scan snapshot blocks in file order the way _convert_depth does.

    Returns per emitted block (first exch_ts, last exch_ts, exch_ts of the row that closes
    it, bid rows, ask rows) and the index of the first block that the one-shot
    _convert_depth would truncate, or -1. A block is emitted when its closing row is read.
    _convert_depth reslices its snapshot buffers to each emitted block's size (even to 0),
    so a later block with more rows on a side than the smallest earlier one is cut short.
    """
    n_max = 0
    for i in range(len(is_snapshot)):
        if is_snapshot[i] == 1 and (i == 0 or is_snapshot[i - 1] == 0):
            n_max += 1
    lo = np.empty(n_max, np.int64)
    hi = np.empty(n_max, np.int64)
    close = np.empty(n_max, np.int64)
    nb = np.empty(n_max, np.int64)
    na = np.empty(n_max, np.int64)
    n, cap_b, cap_a = 0, buffer_size, buffer_size
    in_block, b, a, first, last, truncated = False, 0, 0, 0, 0, -1
    for i in range(len(is_snapshot)):
        if is_snapshot[i] == 1:
            if not in_block:
                in_block, b, a, first = True, 0, 0, exch_ts[i]
            last = exch_ts[i]
            if side[i] == 1:
                b += 1
            else:
                a += 1
        elif in_block:
            in_block = False
            if (b > cap_b or a > cap_a) and truncated < 0:
                truncated = n
            cap_b, cap_a = min(cap_b, b), min(cap_a, a)
            lo[n], hi[n], close[n], nb[n], na[n] = first, last, exch_ts[i], b, a
            n += 1
    return lo[:n], hi[:n], close[:n], nb[:n], na[:n], truncated


def _masked_max(x, mask):
    return int(np.max(x, where=mask, initial=I64.min))


def _masked_min(x, mask):
    return int(np.min(x, where=mask, initial=I64.max))


def find_cuts(trades, depth, n_parts: int, windows_ns: tuple, blocks: list) -> list[int]:
    """Clean cuts nearest to n_parts - 1 equally spaced exchange times.

    Each target tries the windows in order and takes the first that has a clean cut.
    blocks holds (first, last, closing row) exchange times of each snapshot block.
    """
    srcs = [(s["exch_ts"], s["local_ts"]) for s in (trades, depth)]
    t_lo = min(int(e.min()) for e, _ in srcs)
    t_hi = max(int(e.max()) for e, _ in srcs)
    cuts = []
    for k in range(1, n_parts):
        target = t_lo + (t_hi - t_lo) * k // n_parts
        for window_ns in windows_ns:
            cand = _clean_cuts_near(srcs, target, window_ns, blocks)
            if len(cand):
                cuts.append(int(cand[np.argmin(np.abs(cand - target))]))
                break
        else:
            raise ConversionError(f"no clean cut within {max(windows_ns)} ns of {target}")
    return cuts


def _clean_cuts_near(srcs, target: int, window_ns: int, blocks: list) -> np.ndarray:
    w_lo, w_hi = target - window_ns, target + window_ns
    before = max(_masked_max(loc, e < w_lo) for e, loc in srcs)
    after = min(_masked_min(loc, e >= w_hi) for e, loc in srcs)
    e_w = np.concatenate([e[(e >= w_lo) & (e < w_hi)] for e, _ in srcs])
    l_w = np.concatenate([loc[(e >= w_lo) & (e < w_hi)] for e, loc in srcs])
    order = np.argsort(e_w, kind="mergesort")
    e_w, l_w = e_w[order], l_w[order]
    # Cut between sorted positions i and i + 1, at B = e_w[i + 1]: everything sent
    # before B must be received strictly before everything sent at or after B.
    pmax = np.maximum(np.maximum.accumulate(l_w), before)
    smin = np.minimum(np.minimum.accumulate(l_w[::-1])[::-1], after)
    ok = (e_w[:-1] < e_w[1:]) & (pmax[:-1] < smin[1:])
    cand = e_w[1:][ok]
    # A snapshot block and the row that closes it must land in the same part.
    for b_lo, b_hi, b_close in blocks:
        lo, hi = min(b_lo, b_close), max(b_hi, b_close)
        cand = cand[~((cand > lo) & (cand <= hi))]
    return cand


def convert_parts(
    trades_path: Path,
    depth_path: Path,
    n_parts: int | None = None,
    events_per_part: int = 15_000_000,
    chunk_bytes: int = 256 << 20,
    search_windows_us: tuple = (300_000_000, 1_800_000_000),
    sink=None,
) -> tuple[list[np.ndarray], dict]:
    """Return (parts, info). With sink, each part goes to sink(k, part) and is not kept."""
    trades = read_trades(Path(trades_path), chunk_bytes)
    depth = read_depth(Path(depth_path), chunk_bytes)
    if n_parts is None:
        n_parts = max(1, math.ceil((len(trades) + len(depth)) / events_per_part))

    lo, hi, close, nb, na, truncated = _snapshot_blocks(
        depth["exch_ts"], depth["side"], depth["is_snapshot"], SS_BUFFER_SIZE
    )
    if truncated >= 0:
        raise ConversionError(
            f"snapshot block {truncated} has more levels than an earlier one; "
            "hftbacktest's one-shot convert would truncate it"
        )

    # correct_local_timestamp with base_latency = 0: shift every local_ts by the most
    # negative feed latency of the whole day. It must be the day's value, not a part's.
    min_lat = min(int((s["local_ts"] - s["exch_ts"]).min()) for s in (trades, depth))
    offset = -min_lat if min_lat < 0 else 0

    windows_ns = tuple(w * 1000 for w in search_windows_us)
    blocks = list(zip(lo, hi, close, strict=True))
    cuts = find_cuts(trades, depth, n_parts, windows_ns, blocks)
    if any(b <= a for a, b in zip(cuts, cuts[1:], strict=False)):
        raise ConversionError(f"cuts are not strictly increasing: {cuts}")
    edges = [I64.min, *cuts, I64.max]
    parts, sizes, emitted, prev_max_local = [], [], 0, None
    for k in range(n_parts):
        t_seg = trades[(trades["exch_ts"] >= edges[k]) & (trades["exch_ts"] < edges[k + 1])]
        d_seg = depth[(depth["exch_ts"] >= edges[k]) & (depth["exch_ts"] < edges[k + 1])]
        n_snap = int(d_seg["is_snapshot"].sum())
        tmp = np.empty(len(t_seg) + len(d_seg) + 2 * n_snap, event_dtype)
        tmp[: len(t_seg)] = t_seg
        ss_bid = np.empty(SS_BUFFER_SIZE, event_dtype)
        ss_ask = np.empty(SS_BUFFER_SIZE, event_dtype)
        n = _convert_depth(tmp, d_seg, len(t_seg), ss_bid, ss_ask, 0)
        tmp = tmp[:n]
        del d_seg, t_seg
        if n == 0:
            raise ConversionError(f"part {k} is empty")
        # Counted before correct_event_order, which can write a row twice (EXCH and LOCAL).
        emitted += int(((tmp["ev"] & 0xFF) == DEPTH_SNAPSHOT_EVENT).sum())
        # Re-check the cut actually used: this part must start receiving after the
        # previous part finished receiving.
        if prev_max_local is not None and int(tmp["local_ts"].min()) <= prev_max_local:
            raise ConversionError(f"cut {k} is not clean: messages in flight across it")
        prev_max_local = int(tmp["local_ts"].max())
        if offset:
            tmp["local_ts"] += offset
        data = correct_event_order(
            tmp,
            np.argsort(tmp["exch_ts"], kind="mergesort"),
            np.argsort(tmp["local_ts"], kind="mergesort"),
        )
        del tmp
        validate_event_order(data)
        sizes.append(len(data))
        if sink is None:
            parts.append(data)
        else:
            sink(k, data)
        del data

    # The one-shot pass emits every block that some non-snapshot row follows in file
    # order. A part can only emit fewer, so equal totals mean the same blocks.
    if emitted != int(nb.sum() + na.sum()):
        raise ConversionError(
            f"parts emitted {emitted} snapshot rows, the one-shot pass {int(nb.sum() + na.sum())}"
        )

    info = {
        "n_parts": n_parts,
        "cuts": cuts,  # exchange timestamps in ns where each later part starts
        "events_per_part": sizes,
        "trade_rows": len(trades),
        "depth_rows": len(depth),
        "snapshot_blocks": len(lo),
        "snapshot_levels_bid_ask": [[int(b), int(a)] for b, a in zip(nb, na, strict=True)][:10],
        "min_feed_latency_ns": min_lat,
        "local_ts_offset_ns": offset,
        # Tick and lot as the data shows them, over CSV rows (not converted events);
        # tests/unit/test_venue.py compares them with configs/venue.yaml.
        "inferred": infer_from_rows(depth["px"], trades["px"], trades["qty"]),
    }
    return parts, info


def convert_day(
    day: str,
    raw_dir: Path = RAW,
    out_dir: Path = CONVERTED,
    manifest: Path = MANIFEST,
    events_per_part: int = 15_000_000,
) -> Path:
    """Write data/converted/<date>/part-NN.npz and convert.json. Return the directory."""
    assert_allowed(day)  # first: converting reads the raw file
    day = normalise(day)
    dest = out_dir / day
    if (dest / "convert.json").exists():
        return dest
    pinned = {(e["date"], e["data_type"]): e for e in load_manifest(manifest)}
    raw = {}
    for data_type in DATA_TYPES:
        path = raw_dir / day / f"{data_type}.csv.gz"
        entry = pinned.get((day, data_type))
        if entry is None or not path.exists() or sha256_file(path) != entry["sha256"]:
            raise ManifestError(f"{path} is missing or does not match data/manifest.json")
        raw[data_type] = entry

    staging = out_dir / f"{day}.partial"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    def save(k: int, part: np.ndarray) -> None:
        np.savez_compressed(staging / f"part-{k:02d}.npz", data=part)

    start = time.perf_counter()
    # Trades first, as tardis.convert asks, so a trade reduces queue position before the
    # depth update it caused.
    _, info = convert_parts(
        raw_dir / day / "trades.csv.gz",
        raw_dir / day / "incremental_book_L2.csv.gz",
        events_per_part=events_per_part,
        sink=save,
    )
    files = sorted(staging.glob("part-*.npz"))
    conversion_seconds = round(time.perf_counter() - start, 1)
    info.update(
        {
            "date": day,
            "hftbacktest_version": hftbacktest.__version__,
            "raw_sha256": {t: raw[t]["sha256"] for t in DATA_TYPES},
            "raw_bytes": sum(raw[t]["bytes"] for t in DATA_TYPES),
            "files": [f.name for f in files],
            "converted_bytes": sum(f.stat().st_size for f in files),
            "conversion_seconds": conversion_seconds,
            # ru_maxrss is bytes on macOS. Peak of this process so far, so with several
            # days in one make data call it is the largest day up to this one.
            "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
    )
    (staging / "convert.json").write_text(json.dumps(info, indent=2) + "\n")
    os.rename(staging, dest)
    return dest


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    for day in resolve_days(argv[0]):
        try:
            dest = convert_day(day)
        except SplitLockError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        info = json.loads((dest / "convert.json").read_text())
        print(f"{day}: {info['n_parts']} parts, {info['converted_bytes']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
