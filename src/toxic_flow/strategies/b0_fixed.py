"""B0, fixed spread (PREREGISTRATION.md section 4), as a numba loop over hftbacktest.

bid = mid - h ticks rounded down, ask = mid + h ticks rounded up, post-only, one order per
side, cancelled and replaced when the target price changes. No bid at q >= Q, no ask at
q <= -Q.
"""

import math

import numpy as np
from numba import njit

from toxic_flow.strategies.common import both_resting, finish_day, place_quotes, record_fills


@njit(cache=True)
def quote_ticks(best_bid_tick: int, best_ask_tick: int, h: int) -> tuple[int, int]:
    # Twice the mid in ticks is an integer, so the outward rounding is exact.
    two_mid = best_bid_tick + best_ask_tick
    bid = (two_mid - 2 * h) // 2
    ask = -((-(two_mid + 2 * h)) // 2)
    # A bid at or above the best ask moves to one tick below it, and the mirror for asks.
    return min(bid, best_ask_tick - 1), max(ask, best_bid_tick + 1)


@njit(cache=True)
def sides_allowed(position: float, order_qty: float, max_lots: int) -> tuple[bool, bool]:
    q = round(position / order_qty)  # inventory in order sizes; rounding drops float noise
    return q < max_lots, q > -max_lots


@njit(cache=True)
def order_size(price: float, lot_size: float, min_notional: float) -> float:
    """Smallest whole number of lots whose notional at price is at least min_notional."""
    lots = max(1, math.ceil(min_notional / (price * lot_size) - 1e-9))
    return lots * lot_size


@njit
def run_b0(
    hbt,
    h,
    lot_size,
    min_notional,
    max_lots,
    quote_start_ns,
    quote_end_ns,
    step_ns,
    steps,
    fills,
    out,
):
    """Quote from quote_start_ns until quote_end_ns, then cancel everything and mark.

    One order per side at most (strategies.common.place_quotes). The order size is fixed
    for the day at the first quoting step, from the mid seen then, so it uses no later
    price. steps receives one row per quoting step, fills one row per fill. out: 0 steps
    recorded, 1 fills (engine), 2 position, 3 cash, 4 mark mid, 5 order size, 6 most of our
    orders on one side, 7 largest inventory in order sizes, 8 last decision time, 9 mark
    time, 10 fee, 11 traded value, 12 fills recorded.
    """
    order_qty, next_id, n_steps, n_fills = 0.0, 1, 0, 0
    # Warm-up, no orders. Elapse before reading the clock: until the first elapse,
    # hftbacktest reports current_timestamp as i64 max.
    while True:
        if hbt.elapse(step_ns) != 0:
            return
        if hbt.current_timestamp >= quote_start_ns:
            break
    while True:
        if hbt.elapse(step_ns) != 0:
            break
        now = hbt.current_timestamp
        if now >= quote_end_ns:
            break  # no decision at or after quote_end_ns
        n_fills = record_fills(hbt, fills, n_fills)
        hbt.clear_inactive_orders(0)
        depth = hbt.depth(0)
        bb, ba = depth.best_bid_tick, depth.best_ask_tick
        position = hbt.position(0)
        mid, both = np.nan, False
        bid_t, ask_t, n_cancel = np.nan, np.nan, 0
        if np.isfinite(depth.best_bid) and np.isfinite(depth.best_ask) and bb < ba:
            mid = (depth.best_bid + depth.best_ask) / 2.0
            if order_qty == 0.0:
                order_qty = order_size(mid, lot_size, min_notional)
            bid_tick, ask_tick = quote_ticks(bb, ba, h)
            want_bid, want_ask = sides_allowed(position, order_qty, max_lots)
            out[7] = max(out[7], abs(round(position / order_qty)))
            both = both_resting(hbt)
            next_id, n_buy, n_sell, n_cancel = place_quotes(
                hbt, bid_tick, ask_tick, want_bid, want_ask, order_qty, next_id,
                round(position / order_qty), max_lots,
            )  # fmt: skip
            bid_t = bid_tick if want_bid else np.nan
            ask_t = ask_tick if want_ask else np.nan
            out[6] = max(out[6], n_buy, n_sell)
            out[8] = now
        if n_steps < len(steps):
            steps[n_steps].ts = now
            steps[n_steps].mid = mid
            steps[n_steps].position = position
            steps[n_steps].balance = hbt.state_values(0).balance
            steps[n_steps].both_quoted = both
            steps[n_steps].bid_tick, steps[n_steps].ask_tick = bid_t, ask_t
            steps[n_steps].best_bid_tick, steps[n_steps].best_ask_tick = bb, ba
            steps[n_steps].cancels = n_cancel
            n_steps += 1
    out[0] = n_steps
    out[5] = order_qty
    finish_day(hbt, fills, n_fills, out)
