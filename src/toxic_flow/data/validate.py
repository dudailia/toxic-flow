"""Checks on converted data. M0: tick and lot size inferred from the data itself.

M1 adds the per-day data-quality report (crossed books, gaps, feed latency quantiles).
"""

import numpy as np

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
