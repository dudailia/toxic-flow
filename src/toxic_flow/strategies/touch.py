"""v2 strategies (PREREGISTRATION.md section 4) in one numba loop: B0 and B1 join the touch,
and B2, B2b and B3 add the step-back overlay to B1.

    B0: bid = best bid, ask = best ask
    B1: bid = best bid - q, ask = best ask - q            (q: inventory in order sizes)
    overlay: the toxic side (the ask when u > theta_u, the bid when u < -theta_u) steps
             back k_ticks, or is not quoted when k_ticks = PULL; when m > theta_m both
             sides step back one more tick.

Then, as for every strategy, a bid at or above the best ask moves to one tick below it (and
the mirror for asks), and the inventory cap removes a side. theta_u and theta_m are the
training-day quantiles of section 5, carried in the run config. B0 and B1 run with both
thresholds at infinity, so the overlay never acts. C2 (the oracle) is B1 with u from a
series built in tests/canary/: +1 when the mid 5 s ahead is at least one tick higher, -1
when at least one tick lower, else 0; theta_u = 0.5 and k_ticks = PULL.
"""

import numpy as np
from numba import njit

from toxic_flow.signals.normalise import Ring
from toxic_flow.strategies.b0_fixed import order_size, sides_allowed
from toxic_flow.strategies.common import both_resting, finish_day, place_quotes, record_fills
from toxic_flow.strategies.signal_input import NONE, signal_at

PULL = -1  # k_ticks for "pull the side"


@njit(cache=True)
def step_back(bid, ask, u, m, theta_u, k_ticks, theta_m):
    """The overlay on a B1 quote. Returns (bid, ask, quote bid, quote ask, toxic), where
    toxic is +1 when the ask is the toxic side, -1 the bid, 0 neither."""
    toxic = 1 if u > theta_u else (-1 if u < -theta_u else 0)
    if m > theta_m:
        bid, ask = bid - 1, ask + 1
    quote_bid, quote_ask = True, True
    if toxic == 1:
        if k_ticks == PULL:
            quote_ask = False
        else:
            ask += k_ticks
    elif toxic == -1:
        if k_ticks == PULL:
            quote_bid = False
        else:
            bid -= k_ticks
    return bid, ask, quote_bid, quote_ask, toxic


@njit(cache=True)
def touch_quote(bb, ba, q, skew, u, m, theta_u, k_ticks, theta_m):
    """Target ticks of one step: the base (B0, or B1 with skew), the overlay, then the
    cross rule. Returns (bid, ask, quote bid, quote ask, toxic)."""
    s = q if skew else 0
    bid, ask, qb, qa, toxic = step_back(bb - s, ba - s, u, m, theta_u, k_ticks, theta_m)
    return min(bid, ba - 1), max(ask, bb + 1), qb, qa, toxic


@njit
def run_touch(
    hbt, lot_size, min_notional, max_lots, quote_start_ns, quote_end_ns, step_ns,
    steps, fills, out,
    skew, mode, K, norm_steps, sig_ts, sig_side, sig_cum, tau_s, ofi_window_ns,
    mu, alpha, beta, ext_u, ext_m, theta_u, k_ticks, theta_m, diag,
):  # fmt: skip
    """Quote from quote_start_ns until quote_end_ns, then cancel everything and mark. out as
    in strategies.b0_fixed.run_b0. The signal is computed at every step from the start of
    the data, warm-up included; diag receives (time, u, m) per step while it has room."""
    order_qty, next_id, n_steps, n_fills, n_diag = 0.0, 1, 0, 0, 0
    a_ring, ofi_ring = Ring(norm_steps), Ring(norm_steps)
    state, lam = np.zeros(4), np.empty(2)
    pos = np.zeros(3, np.int64)
    while True:
        if hbt.elapse(step_ns) != 0:
            break
        now = hbt.current_timestamp
        if now >= quote_end_ns:
            break
        u, m = 0.0, 0.0
        if mode != NONE:
            u, m = signal_at(
                now, mode, pos, state, lam, a_ring, ofi_ring, K, sig_ts, sig_side, sig_cum,
                tau_s, ofi_window_ns, mu, alpha, beta, ext_u, ext_m,
            )  # fmt: skip
        if n_diag < len(diag):
            diag[n_diag, 0], diag[n_diag, 1], diag[n_diag, 2] = now, u, m
            n_diag += 1
        if now < quote_start_ns:
            continue  # warm-up: signal and normalisers only, no orders

        n_fills = record_fills(hbt, fills, n_fills)
        hbt.clear_inactive_orders(0)
        dp = hbt.depth(0)
        bb, ba = dp.best_bid_tick, dp.best_ask_tick
        position = hbt.position(0)
        mid, both, toxic = np.nan, False, 0
        bid_rec, ask_rec, n_cancel = np.nan, np.nan, 0
        if np.isfinite(dp.best_bid) and np.isfinite(dp.best_ask) and bb < ba:
            mid = (dp.best_bid + dp.best_ask) / 2.0
            if order_qty == 0.0:
                order_qty = order_size(mid, lot_size, min_notional)
            q = round(position / order_qty)  # whole order sizes; rounding drops float noise
            bid_t, ask_t, qb, qa, toxic = touch_quote(
                bb, ba, q, skew, u, m, theta_u, k_ticks, theta_m
            )
            want_bid, want_ask = sides_allowed(position, order_qty, max_lots)
            want_bid, want_ask = want_bid and qb, want_ask and qa
            bid_rec = bid_t if want_bid else np.nan
            ask_rec = ask_t if want_ask else np.nan
            both = both_resting(hbt)
            next_id, n_buy, n_sell, n_cancel = place_quotes(
                hbt, bid_t, ask_t, want_bid, want_ask, order_qty, next_id, q, max_lots
            )
            out[6] = max(out[6], n_buy, n_sell)
            out[7] = max(out[7], abs(q))
            out[8] = now
        if n_steps < len(steps):
            steps[n_steps].ts = now
            steps[n_steps].mid = mid
            steps[n_steps].position = position
            steps[n_steps].balance = hbt.state_values(0).balance
            steps[n_steps].both_quoted = both
            steps[n_steps].bid_tick, steps[n_steps].ask_tick = bid_rec, ask_rec
            steps[n_steps].best_bid_tick, steps[n_steps].best_ask_tick = bb, ba
            steps[n_steps].cancels = n_cancel
            steps[n_steps].toxic = toxic
            n_steps += 1
    out[0] = n_steps
    out[5] = order_qty
    finish_day(hbt, fills, n_fills, out)
