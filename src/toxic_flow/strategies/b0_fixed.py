"""B0, fixed spread (PREREGISTRATION.md section 4), as a numba loop over hftbacktest.

bid = mid - h ticks rounded down, ask = mid + h ticks rounded up, post-only, one order per
side, cancelled and replaced when the target price changes. No bid at q >= Q, no ask at
q <= -Q. M0 uses it as the one-day benchmark; M2 extends it with the per-step records.
"""

import math

import numpy as np
from hftbacktest import BUY, GTX, LIMIT, SELL
from numba import njit


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
def run_b0(hbt, h, lot_size, min_notional, max_lots, quote_start_ns, quote_end_ns, step_ns, out):
    """Quote from quote_start_ns to quote_end_ns, then cancel everything.

    The order size is fixed for the day at the first quoting step, from the mid seen then,
    so it uses no later price. out receives: steps quoted, fills, position, cash balance,
    mid at the end, order size.
    """
    asset = 0
    steps = 0
    order_qty = 0.0
    # Warm-up, no orders. Elapse before reading the clock: until the first elapse,
    # hftbacktest reports current_timestamp as i64 max.
    while True:
        if hbt.elapse(step_ns) != 0:
            return
        if hbt.current_timestamp >= quote_start_ns:
            break
    while hbt.current_timestamp < quote_end_ns:
        if hbt.elapse(step_ns) != 0:
            break
        hbt.clear_inactive_orders(asset)
        depth = hbt.depth(asset)
        bb, ba = depth.best_bid_tick, depth.best_ask_tick
        if not (np.isfinite(depth.best_bid) and np.isfinite(depth.best_ask)) or bb >= ba:
            continue
        steps += 1
        if order_qty == 0.0:
            order_qty = order_size((depth.best_bid + depth.best_ask) / 2.0, lot_size, min_notional)
        bid_tick, ask_tick = quote_ticks(bb, ba, h)
        want_bid, want_ask = sides_allowed(hbt.position(asset), order_qty, max_lots)

        # Order id = price tick: at most one of our orders per price, and a bid can never
        # share a tick with an ask because bid_tick < ask_tick.
        orders = hbt.orders(asset)
        values = orders.values()
        while values.has_next():
            o = values.get()
            if not o.cancellable:
                continue
            if o.side == BUY and (not want_bid or o.price_tick != bid_tick):
                hbt.cancel(asset, o.order_id, False)
            elif o.side == SELL and (not want_ask or o.price_tick != ask_tick):
                hbt.cancel(asset, o.order_id, False)
        tick = depth.tick_size
        if want_bid and not orders.__contains__(bid_tick):
            hbt.submit_buy_order(asset, bid_tick, bid_tick * tick, order_qty, GTX, LIMIT, False)
        if want_ask and not orders.__contains__(ask_tick):
            hbt.submit_sell_order(asset, ask_tick, ask_tick * tick, order_qty, GTX, LIMIT, False)

    # End of the quoting window: cancel all resting orders and let the cancels land.
    values = hbt.orders(asset).values()
    while values.has_next():
        o = values.get()
        if o.cancellable:
            hbt.cancel(asset, o.order_id, False)
    hbt.elapse(1_000_000_000)
    depth = hbt.depth(asset)
    sv = hbt.state_values(asset)
    out[0] = steps
    out[1] = sv.num_trades
    out[2] = sv.position
    out[3] = sv.balance
    out[4] = (depth.best_bid + depth.best_ask) / 2.0
    out[5] = order_qty
