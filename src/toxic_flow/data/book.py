"""Best bid and offer as the strategy would see them, from hftbacktest's own book.

The converted events are replayed through HashMapMarketDepthBacktest with no orders.
wait_next_feed returns once per distinct local timestamp (every event received at the
same instant is applied together), so each row here is one moment the strategy could
observe. Using the engine's book, not a separate one, keeps snapshot and clear handling
identical to the simulation.

The engine never shows best bid >= best ask: an update that crosses the book moves the
opposite best past it (HashMapMarketDepth::update_bid_depth and update_ask_depth), often
to "no level", and that side stays empty until its next update. So "crossed" here means
an opposite-side level hidden within OVERLAP_TICKS of the touch, and one-sided batches
are counted too. An overlap deeper than OVERLAP_TICKS is not seen. The last batch of the
data is applied but returned as end of data, so it is not a row.
"""

from pathlib import Path

import numpy as np
from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
from numba import njit

BBO_DTYPE = np.dtype(
    [("local_ts", "i8"), ("bid_px", "f8"), ("bid_qty", "f8"), ("ask_px", "f8"), ("ask_qty", "f8")]
)
FOREVER_NS = 86_400 * 10**9 * 365  # wait_next_feed timeout longer than any data
OVERLAP_TICKS = 10


@njit
def _crossed(d, k_max):
    if np.isfinite(d.best_bid):
        for k in range(k_max + 1):
            if d.ask_qty_at_tick(d.best_bid_tick - k) > 0:
                return True
    if np.isfinite(d.best_ask):
        for k in range(k_max + 1):
            if d.bid_qty_at_tick(d.best_ask_tick + k) > 0:
                return True
    return False


@njit
def _replay_chunk(hbt, buf, counts, k_max):
    """Fill buf with one row per feed batch that has both sides. counts: batches,
    crossed, one-sided, 1 when the data has ended, an unexpected return code."""
    n = 0
    while n < len(buf):
        code = hbt.wait_next_feed(False, FOREVER_NS)
        if code == 1:
            counts[3] = 1
            return n
        if code != 2:
            counts[4] = code
            return n
        counts[0] += 1
        d = hbt.depth(0)
        if _crossed(d, k_max):
            counts[1] += 1
        bid_ok, ask_ok = np.isfinite(d.best_bid), np.isfinite(d.best_ask)
        if bid_ok != ask_ok:
            counts[2] += 1
        if not (bid_ok and ask_ok):
            continue
        buf[n].local_ts = hbt.current_timestamp
        buf[n].bid_px = d.best_bid
        buf[n].bid_qty = d.best_bid_qty
        buf[n].ask_px = d.best_ask
        buf[n].ask_qty = d.best_ask_qty
        n += 1
    return n


def replay_bbo(
    part_files: list[Path], tick_size: float, lot_size: float, chunk: int = 1_000_000
) -> tuple[np.ndarray, dict]:
    """(rows of BBO_DTYPE, {"batches", "crossed", "one_sided"}) over one day's parts."""
    asset = (
        BacktestAsset()
        # Paths, or arrays the caller keeps alive for the whole replay: hftbacktest keeps a
        # raw pointer to an array instead of copying it.
        .data([p if isinstance(p, np.ndarray) else str(p) for p in part_files])
        .linear_asset(1.0)
        .constant_order_latency(0, 0)
        .risk_adverse_queue_model()
        .no_partial_fill_exchange()
        .trading_value_fee_model(0.0, 0.0)
        .tick_size(tick_size)
        .lot_size(lot_size)
    )
    hbt = HashMapMarketDepthBacktest([asset])
    counts = np.zeros(5, np.int64)
    pieces = []
    try:
        while counts[3] == 0:
            buf = np.empty(chunk, BBO_DTYPE)
            n = _replay_chunk(hbt, buf, counts, OVERLAP_TICKS)
            if counts[4] != 0:
                raise RuntimeError(f"wait_next_feed returned {counts[4]}")
            pieces.append(buf[:n].copy())
    finally:
        hbt.close()
    stats = {"batches": int(counts[0]), "crossed": int(counts[1]), "one_sided": int(counts[2])}
    return np.concatenate(pieces), stats
