"""Pieces every strategy loop shares: per-step and per-fill records, quote placement with
one order per side, and the end of the quoting window. All numba, for hftbacktest."""

import numpy as np
from hftbacktest import BUY, CANCELED, FILLED, GTX, LIMIT, NEW
from numba import njit

# bid_tick and ask_tick are the step's target quotes (NaN for a side not quoted), best_*
# the book's best prices, cancels the cancels sent that step: diagnostics only (M4
# diagnosis, 2026-10-24); no metric of section 6 reads them.
STEP_DTYPE = np.dtype(
    [("ts", "i8"), ("mid", "f8"), ("position", "f8"), ("balance", "f8"), ("both_quoted", "?"),
     ("bid_tick", "f8"), ("ask_tick", "f8"), ("best_bid_tick", "f8"), ("best_ask_tick", "f8"),
     ("cancels", "i4")]
)  # fmt: skip
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
def both_resting(hbt):
    """Whether an order of ours rests in the book on both sides, as the local side last
    heard: status NEW, so acknowledged and not yet seen filled or cancelled. Called before
    the step sends anything; an order just sent rests only once its ack comes back.
    Quote presence (PREREGISTRATION.md section 6) is the share of steps where this holds."""
    bid, ask = False, False
    values = hbt.orders(0).values()
    while values.has_next():
        o = values.get()
        if o.status == NEW:
            if o.side == BUY:
                bid = True
            else:
                ask = True
    return bid and ask


@njit
def place_quotes(hbt, bid_tick, ask_tick, want_bid, want_ask, qty, next_id, q_lots, max_lots):
    """At most one working order per side, replaced in the same step (Q31). Each step,
    per side: an order at the target price stays; a stale one is cancelled and, in the
    same step, its replacement is sent. Two things hold a replacement back: an earlier
    order on that side not yet acknowledged (it cannot be cancelled yet), and the
    inventory cap, which counts every open order on the side, cancels in flight
    included, as if all of them filled: a bid goes out only if q + open bids + 1 <= Q.
    q_lots is the inventory in order sizes. Returns (next order id, our buy orders, our
    sell orders as seen before sending, cancels sent)."""
    n_buy, n_sell, n_cancel = 0, 0, 0
    keep_buy, keep_sell = False, False  # an order already at the target price
    wait_buy, wait_sell = False, False  # an unacknowledged order that cannot be cancelled
    values = hbt.orders(0).values()
    while values.has_next():
        o = values.get()
        buy = o.side == BUY
        if buy:
            n_buy += 1
        else:
            n_sell += 1
        if o.req == CANCELED:
            continue  # its cancel is in flight; it still counts against the cap
        want, target = (want_bid, bid_tick) if buy else (want_ask, ask_tick)
        if want and o.price_tick == target:
            if buy:
                keep_buy = True
            else:
                keep_sell = True
        elif o.cancellable:
            hbt.cancel(0, o.order_id, False)
            n_cancel += 1
        elif buy:
            wait_buy = True
        else:
            wait_sell = True
    tick = hbt.depth(0).tick_size
    if want_bid and not keep_buy and not wait_buy and q_lots + n_buy + 1 <= max_lots:
        hbt.submit_buy_order(0, next_id, bid_tick * tick, qty, GTX, LIMIT, False)
        next_id += 1
    if want_ask and not keep_sell and not wait_sell and -q_lots + n_sell + 1 <= max_lots:
        hbt.submit_sell_order(0, next_id, ask_tick * tick, qty, GTX, LIMIT, False)
        next_id += 1
    return next_id, n_buy, n_sell, n_cancel


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
