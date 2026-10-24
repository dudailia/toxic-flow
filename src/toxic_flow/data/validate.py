"""Checks on converted data: tick and lot inferred from the data, and the per-day
data-quality report (crossed books, largest gaps, feed latency, counts).

Usage: uv run python -m toxic_flow.data.validate YYYY-MM-DD
Writes docs/data_quality/<date>.json.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from hftbacktest import DEPTH_EVENT, DEPTH_SNAPSHOT_EVENT, LOCAL_EVENT, TRADE_EVENT

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / "docs" / "data_quality"
GAP_RULE_S = 600  # exclusion rule 3: a gap longer than 10 minutes in the quoting window

DECIMALS = 9  # rounding that removes float noise such as 42314.100000000006


def infer_increment(values: np.ndarray, counts: np.ndarray | None = None) -> tuple[float, int]:
    """Most common gap between adjacent distinct values, and the rows not on that grid.

    For book prices this is the tick size, for trade quantities the lot size. The most
    common gap rather than the smallest, because a few hundred off-grid prints among
    96M book rows on 2024-01-01 would otherwise set the tick; they are counted instead.
    """
    if counts is None:
        values, counts = np.unique(np.round(values, DECIMALS), return_counts=True)
    if len(values) < 2:
        return float("nan"), 0  # no gap to measure; the venue check then fails loudly
    gaps, n = np.unique(np.round(np.diff(values), DECIMALS), return_counts=True)
    step = float(gaps[np.argmax(n)])
    off = np.abs(values / step - np.round(values / step)) > 1e-6
    return step, int(counts[off].sum())


def infer_from_rows(book_px: np.ndarray, trade_px: np.ndarray, trade_qty: np.ndarray) -> dict:
    """Tick from book prices, lot from trade sizes, and the rows off each grid."""
    tick, book_off = infer_increment(book_px)
    lot, qty_off = infer_increment(trade_qty)
    p = np.round(trade_px, DECIMALS)
    trade_off_tick = int((np.abs(p / tick - np.round(p / tick)) > 1e-6).sum())
    return {
        "tick_size": tick,
        "book_rows": len(book_px),
        "book_rows_off_tick_grid": book_off,
        "trade_rows": len(trade_px),
        "trade_rows_off_tick_grid": trade_off_tick,
        "lot_size": lot,
        "trade_rows_off_lot_grid": qty_off,
    }


def largest_gap(local_ts: np.ndarray, start: int, end: int) -> tuple[float, int]:
    """Longest stretch in [start, end] with no event, in seconds, and where it begins.
    The window edges count, so a stream that is silent at the start or end shows it."""
    t = np.sort(local_ts[(local_ts >= start) & (local_ts <= end)])
    edges = np.concatenate([[start], t, [end]]).astype(np.int64)
    gaps = np.diff(edges)
    i = int(np.argmax(gaps))
    return float(gaps[i]) / 1e9, int(edges[i])


class GapTracker:
    """largest_gap fed one time-ordered piece at a time, so a day never has to be held:
    received events are in local-time order within each converted part and across parts.
    ValueError if a piece breaks the order."""

    def __init__(self, start: int, end: int):
        self.start, self.end = start, end
        self.best, self.at, self.prev = -1, start, start

    def add(self, t: np.ndarray) -> None:
        t = t[(t >= self.start) & (t <= self.end)]
        if not len(t):
            return
        if t[0] < self.prev or (np.diff(t) < 0).any():
            raise ValueError("pieces are not in time order")
        edges = np.concatenate([[self.prev], t]).astype(np.int64)
        gaps = np.diff(edges)
        i = int(np.argmax(gaps))
        if gaps[i] > self.best:  # strict: the first of equal gaps wins, as in largest_gap
            self.best, self.at = int(gaps[i]), int(edges[i])
        self.prev = int(t[-1])

    def result(self) -> tuple[float, int]:
        best, at = self.best, self.at
        if self.end - self.prev > best:
            best, at = self.end - self.prev, self.prev
        return float(best) / 1e9, int(at)


def largest_gap_sorted(pieces, start: int, end: int) -> tuple[float, int]:
    tracker = GapTracker(start, end)
    for t in pieces:
        tracker.add(t)
    return tracker.result()


def latency_quantiles_ms(latency_ns: np.ndarray) -> dict:
    q = np.percentile(latency_ns, [50, 90, 99]) / 1e6
    return {
        "p50": round(float(q[0]), 3),
        "p90": round(float(q[1]), 3),
        "p99": round(float(q[2]), 3),
        "max": round(float(latency_ns.max()) / 1e6, 3),
    }


class LatencyCounts:
    """latency_quantiles_ms from value counts merged part by part, so a day's latencies are
    never held at once. Exact: latencies are whole microseconds, so a day has few distinct
    values, and the quantiles use numpy's own linear rule on the sorted order."""

    def __init__(self):
        self.values = np.empty(0, np.int64)
        self.counts = np.empty(0, np.int64)

    def add(self, latency_ns: np.ndarray) -> None:
        v, c = np.unique(latency_ns, return_counts=True)
        allv, inv = np.unique(np.concatenate([self.values, v]), return_inverse=True)
        self.counts = np.bincount(inv, weights=np.concatenate([self.counts, c])).astype(np.int64)
        self.values = allv

    def _at(self, cum, k: int) -> float:
        return float(self.values[np.searchsorted(cum, k, side="right")])

    def quantiles_ms(self) -> dict:
        cum = np.cumsum(self.counts)
        n = int(cum[-1])
        out = {}
        for name, q in (("p50", 0.5), ("p90", 0.9), ("p99", 0.99)):
            virtual = (n - 1) * q  # numpy's "linear" method
            lo = int(np.floor(virtual))
            hi = min(lo + 1, n - 1)
            t = virtual - lo
            a, b = self._at(cum, lo), self._at(cum, hi)
            diff = b - a
            v = b - diff * (1 - t) if t >= 0.5 else a + diff * t  # numpy's _lerp
            out[name] = round(v / 1e6, 3)
        out["max"] = round(float(self.values[-1]) / 1e6, 3)
        return out


def quality_report(
    part_files: list, tick: float, lot: float, window: tuple[int, int], bbo_out: list | None = None
):
    """Data quality of one converted day, from the events as the strategy receives them
    (rows flagged LOCAL_EVENT, so each original row counts once). Parts are files or
    in-memory arrays; bbo_out, if given, receives the replayed BBO rows for reuse."""
    from toxic_flow.data.book import replay_bbo

    streams = {"book": DEPTH_EVENT, "trades": TRADE_EVENT}
    gaps = {k: GapTracker(*window) for k in streams}  # part by part, not the whole day
    counts = dict.fromkeys(streams, 0)
    lats = {k: LatencyCounts() for k in streams}
    snapshot_rows = 0
    for f in part_files:
        data = f if isinstance(f, np.ndarray) else np.load(f)["data"]
        local = (data["ev"] & LOCAL_EVENT) == LOCAL_EVENT
        kind = data["ev"] & 0xFF
        for name, code in streams.items():
            rows = data[local & (kind == code)]
            gaps[name].add(rows["local_ts"])
            counts[name] += len(rows)
            lats[name].add(rows["local_ts"] - rows["exch_ts"])
        snapshot_rows += int((local & (kind == DEPTH_SNAPSHOT_EVENT)).sum())
        del data
    rows_bbo, bbo = replay_bbo(part_files, tick, lot)
    if bbo_out is not None:
        bbo_out.append(rows_bbo)
    gaps = {k: g.result() for k, g in gaps.items()}
    return {
        "quoting_window_ns": list(window),
        "book_updates": counts["book"],
        "snapshot_rows": snapshot_rows,
        "trades": counts["trades"],
        "feed_latency_ms": {k: v.quantiles_ms() for k, v in lats.items()},
        "largest_gap_s": {k: round(g, 3) for k, (g, _) in gaps.items()},
        "largest_gap_starts_utc": {
            k: datetime.fromtimestamp(at / 1e9, UTC).isoformat(timespec="milliseconds")
            for k, (_, at) in gaps.items()
        },
        "feed_batches": bbo["batches"],
        # See toxic_flow/data/book.py: an opposite level hidden within 10 ticks of the touch.
        "crossed_book_batches": bbo["crossed"],
        "one_sided_book_batches": bbo["one_sided"],
        "exclusion_rule_3": any(g > GAP_RULE_S for g, _ in gaps.values()),
    }


def write_report(day: str, parts=None, info=None, bbo_out=None) -> Path:
    """docs/data_quality/<day>.json from data/converted/<day> and the raw trades, or from
    a conversion held in memory (parts and its info dict) when the disk has no room."""
    from toxic_flow.data.convert import CONVERTED
    from toxic_flow.data.split_lock import assert_allowed, normalise
    from toxic_flow.data.venue import venue_for
    from toxic_flow.events.market_orders import build_day

    assert_allowed(day)
    day = normalise(day)
    venue = venue_for(day)
    if parts is None:
        conv = json.loads((CONVERTED / day / "convert.json").read_text())
        parts = [CONVERTED / day / f for f in conv["files"]]
    else:
        conv = info
    start = int(datetime.fromisoformat(f"{day}T00:30:00+00:00").timestamp()) * 10**9
    end = int(datetime.fromisoformat(f"{day}T23:59:00+00:00").timestamp()) * 10**9
    report = {
        "date": day,
        "exclusion_rule_1": False,  # both files were downloaded with HTTP 200 (manifest)
        "exclusion_rule_2": False,  # conversion succeeded (else this line is not reached)
        **quality_report(parts, venue["tick_size"], venue["lot_size"], (start, end), bbo_out),
        "inferred": conv["inferred"],
        "local_ts_offset_ns": conv["local_ts_offset_ns"],
        "market_orders": build_day(day, offset_ns=conv["local_ts_offset_ns"]),
    }
    QUALITY.mkdir(parents=True, exist_ok=True)
    out = QUALITY / f"{day}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    return out


if __name__ == "__main__":
    print(write_report(sys.argv[1]))
