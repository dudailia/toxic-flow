"""Pieces every strategy loop shares: per-step and per-fill records, quote placement with
one order per side, and the end of the quoting window. All numba, for hftbacktest."""

import numpy as np
from hftbacktest import BUY, FILLED, GTX, LIMIT
from numba import njit

STEP_DTYPE = np.dtype(
    [("ts", "i8"), ("mid", "f8"), ("position", "f8"), ("balance", "f8"), ("both_quoted", "?")]
)
FILL_DTYPE = np.dtype(
    [
        ("exch_ts", "i8"),
        ("local_ts", "i8"),
        ("side", "i1"),
        ("price", "f8"),
        ("qty", "f8"),
        ("order_id", "i8"),
    ]
)


@njit
def record_fills(hbt, fills, n):
    """Append our orders the local side now sees as FILLED; return the new count.

    Called just before clear_inactive_orders, which drops them, so each fill is read once.
    NoPartialFillExchange fills an order whole, so FILLED is the only fill status here.
    """
    values = hbt.orders(0).values()
    while values.has_next():
        o = values.get()
        if o.status == FILLED and n < len(fills):
            fills[n].exch_ts = o.exch_timestamp
            fills[n].local_ts = o.local_timestamp
            fills[n].side = o.side
            fills[n].price = o.exec_price
            fills[n].qty = o.exec_qty
            fills[n].order_id = o.order_id
            n += 1
    return n


@njit
def place_quotes(hbt, bid_tick, ask_tick, want_bid, want_ask, qty, next_id):
    """At most one order per side. Cancel an order whose price is stale or whose side is no
    longer wanted; send a new one only when that side has no order of ours at all, so a
    replace waits for its cancel and in-flight orders cannot breach the inventory cap.
    Returns (next order id, our buy orders, our sell orders) as seen before sending."""
    n_buy, n_sell = 0, 0
    values = hbt.orders(0).values()
    while values.has_next():
        o = values.get()
        if o.side == BUY:
            n_buy += 1
            stale = not want_bid or o.price_tick != bid_tick
        else:
            n_sell += 1
            stale = not want_ask or o.price_tick != ask_tick
        if stale and o.cancellable:
            hbt.cancel(0, o.order_id, False)
    tick = hbt.depth(0).tick_size
    if want_bid and n_buy == 0:
        hbt.submit_buy_order(0, next_id, bid_tick * tick, qty, GTX, LIMIT, False)
        next_id += 1
    if want_ask and n_sell == 0:
        hbt.submit_sell_order(0, next_id, ask_tick * tick, qty, GTX, LIMIT, False)
        next_id += 1
    return next_id, n_buy, n_sell


@njit
def finish_day(hbt, fills, n_fills, out):
    """Quote end: mark at the mid now, cancel every order, let the cancels land (fills in
    that second still count), then store the totals. out: see the strategy's docstring."""
    depth = hbt.depth(0)
    out[4] = (depth.best_bid + depth.best_ask) / 2.0
    out[9] = hbt.current_timestamp
    values = hbt.orders(0).values()
    while values.has_next():
        o = values.get()
        if o.cancellable:
            hbt.cancel(0, o.order_id, False)
    hbt.elapse(1_000_000_000)
    n_fills = record_fills(hbt, fills, n_fills)
    sv = hbt.state_values(0)
    out[1] = sv.num_trades
    out[2] = sv.position
    out[3] = sv.balance
    out[10] = sv.fee
    out[11] = sv.trading_value
    out[12] = n_fills
    return n_fills
