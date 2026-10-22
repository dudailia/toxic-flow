"""Checks on converted data. M0: tick and lot size inferred from the data itself.

M1 adds the per-day data-quality report (crossed books, gaps, feed latency quantiles).
"""

from pathlib import Path

import numpy as np
from hftbacktest import DEPTH_EVENT, DEPTH_SNAPSHOT_EVENT, TRADE_EVENT

DECIMALS = 9  # rounding that removes float noise such as 42314.100000000006


def infer_increment(values: np.ndarray, counts: np.ndarray | None = None) -> tuple[float, int]:
    """Most common gap between adjacent distinct values, and the rows not on that grid.

    For book prices this is the tick size, for trade quantities the lot size. The most
    common gap rather than the smallest, because a handful of off-grid prints (233 of
    97.8M book rows on 2024-01-01) would otherwise set the tick; they are counted instead.
    """
    if counts is None:
        values, counts = np.unique(np.round(values, DECIMALS), return_counts=True)
    gaps, n = np.unique(np.round(np.diff(values), DECIMALS), return_counts=True)
    step = float(gaps[np.argmax(n)])
    off = np.abs(values / step - np.round(values / step)) > 1e-6
    return step, int(counts[off].sum())


def _merge(uniques: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    values = np.concatenate([u for u, _ in uniques])
    counts = np.concatenate([c for _, c in uniques])
    merged, inverse = np.unique(values, return_inverse=True)
    return merged, np.bincount(inverse, weights=counts).astype(np.int64)


def infer_tick_and_lot(part_files: list[Path]) -> dict:
    """Tick from every book price and lot from every trade quantity of one day."""
    prices, qtys = [], []
    for f in part_files:
        data = np.load(f)["data"]
        kind = data["ev"] & 0xFF
        book = (kind == DEPTH_EVENT) | (kind == DEPTH_SNAPSHOT_EVENT)
        prices.append(np.unique(np.round(data["px"][book], DECIMALS), return_counts=True))
        qtys.append(
            np.unique(np.round(data["qty"][kind == TRADE_EVENT], DECIMALS), return_counts=True)
        )
        del data
    px, px_n = _merge(prices)
    qty, qty_n = _merge(qtys)
    tick, px_off = infer_increment(px, px_n)
    lot, qty_off = infer_increment(qty, qty_n)
    return {
        "tick_size": tick,
        "book_rows": int(px_n.sum()),
        "book_rows_off_tick_grid": px_off,
        "lot_size": lot,
        "trade_rows": int(qty_n.sum()),
        "trade_rows_off_lot_grid": qty_off,
    }
