"""Canary C2, the oracle (PREREGISTRATION.md section 10): the B1 overlay with u = sign of the
mid change over the next 5 s, m = 0 and c = 1. It is the only code in the repo allowed to
build a forward-looking array (SPEC.md AC3.6), and it lives here, outside src/. The
strategy loop reads the series only at points at or before now (overlay mode EXTERNAL),
so the look-ahead is entirely in future_mid below. If C2 cannot beat B1 by a wide margin,
the harness cannot turn information into PnL and a null result would mean nothing.
"""

import numpy as np

HORIZON_S = 5.0


def oracle_series(bbo: np.ndarray, grid: np.ndarray, horizon_s: float = HORIZON_S):
    """(grid times, u, m): u = sign(mid at t + horizon - mid at t), 0 when the data ends
    before t + horizon; m = 0."""
    mid = (bbo["bid_px"] + bbo["ask_px"]) / 2
    now_i = np.searchsorted(bbo["local_ts"], grid, side="right") - 1
    ahead = grid + int(horizon_s * 1e9)
    fut_i = np.searchsorted(bbo["local_ts"], ahead, side="right") - 1
    known = (now_i >= 0) & (ahead <= bbo["local_ts"][-1])
    future_mid = np.where(known, mid[np.clip(fut_i, 0, None)], np.nan)
    u = np.where(known, np.sign(future_mid - mid[np.clip(now_i, 0, None)]), 0.0)
    return grid, u, np.zeros(len(grid))


def oracle_for_day(day: str, cfg: dict):
    """The oracle series on the config's decision grid for one day (engine's oracle hook)."""
    from toxic_flow.data.book import replay_bbo
    from toxic_flow.data.venue import venue_for
    from toxic_flow.engine.run import day_parts, utc_ns

    venue = venue_for(day)
    bbo, _ = replay_bbo(day_parts(day), venue["tick_size"], venue["lot_size"])
    step = int(cfg["step_ns"])
    grid = np.arange(utc_ns(day, "00:00:00"), utc_ns(day, "23:59:00"), step, dtype=np.int64)
    return oracle_series(bbo, grid)


def run_loop_on_file(path, ts, u, m, touch=False, with_steps=False):
    """The C2 loop on one synthetic event file; returns (time, u, m) for every step, and
    the step records too when with_steps. touch quotes at the best prices (no GLFT fit
    needed), which lets a short synthetic day show where the loop puts its quotes."""
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest

    from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE
    from toxic_flow.strategies.overlay import EXTERNAL, run_overlay

    asset = (
        BacktestAsset().data([str(path)]).linear_asset(1.0).constant_order_latency(1_000_000, 1_000_000)
        .risk_adverse_queue_model().no_partial_fill_exchange().trading_value_fee_model(0.0, 0.0)
        .tick_size(0.05).lot_size(0.001).last_trades_capacity(1000)
    )  # fmt: skip
    hbt = HashMapMarketDepthBacktest([asset])
    diag = np.zeros((1000, 3))
    steps, out = np.zeros(1000, STEP_DTYPE), np.zeros(13)
    t0 = int(ts[0])
    run_overlay(
        hbt, 0.05, 6000, 50, 0.001, 100.0, 10, t0 + 10**9, t0 + 5 * 10**9, 100_000_000,
        steps, np.zeros(1000, FILL_DTYPE), out,
        EXTERNAL, 1.0, 0.0, 1.0, 18_000, ts, np.zeros(len(ts), np.int64), np.zeros(1), 1.0, 1,
        np.zeros(2), np.zeros((2, 2)), 1.0, u, m, diag, touch,
    )  # fmt: skip
    hbt.close()
    diag = diag[: int(np.count_nonzero(diag[:, 0]))]
    return (diag, steps[: int(out[0])], out[5]) if with_steps else diag
