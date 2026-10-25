"""Each day's mid on the 100 ms decision grid, saved next to its converted parts for the
exploratory signal-information study (M4 diagnosis, items 6 to 8). Backward-looking only:
the mid at t is the last book state received at or before t. The file survives eviction,
like ofi_contributions.npz, so the study needs no second conversion.
"""

import subprocess
import sys

import numpy as np

from toxic_flow.data.convert import CONVERTED

STEP_NS = 100_000_000


def mid_grid(bbo: np.ndarray, start_ns: int, end_ns: int, step_ns: int = STEP_NS):
    """(grid, mid): mid of the last BBO row with local_ts at or before each grid time, NaN
    before the first row or where the book is crossed or one-sided."""
    grid = np.arange(start_ns, end_ns, step_ns, dtype=np.int64)
    i = np.searchsorted(bbo["local_ts"], grid, side="right") - 1
    bid, ask = bbo["bid_px"][np.clip(i, 0, None)], bbo["ask_px"][np.clip(i, 0, None)]
    ok = (i >= 0) & np.isfinite(bid) & np.isfinite(ask) & (bid < ask)
    return grid, np.where(ok, (bid + ask) / 2, np.nan)


def save(day: str) -> None:
    from toxic_flow.data.book import replay_bbo
    from toxic_flow.data.venue import venue_for
    from toxic_flow.engine.run import day_parts, utc_ns

    venue = venue_for(day)
    bbo, _ = replay_bbo(day_parts(day), venue["tick_size"], venue["lot_size"])
    ts, mid = mid_grid(bbo, utc_ns(day, "00:00:00"), utc_ns(day, "23:59:00"))
    np.savez_compressed(CONVERTED / day / "mid_100ms.npz", ts=ts, mid=mid)


def save_in_child(day: str) -> None:
    """The engine's after_day hook: a child process, so the replay's memory never adds to
    the run's."""
    if (CONVERTED / day / "mid_100ms.npz").exists():
        return
    code = f"from toxic_flow.data.mids import save; save({day!r})"
    subprocess.run([sys.executable, "-c", code], check=True)
