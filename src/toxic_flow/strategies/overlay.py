"""B1 and its overlays B2, B2b, B3 (PREREGISTRATION.md section 4) in one numba loop.

    centre = r + c * u * delta,   bid = centre - delta (1 + d m),   ask = centre + delta (1 + d m)

r and delta come from GLFT (strategies.b1_glft); u in [-1, 1] and m in [0, 1] from the
signal (section 5). Prices round outward, a quote that would cross moves one tick inside
the other side, and the inventory cap removes a side. With c = d = 0 every overlay is B1,
so B1 runs as mode NONE of this loop.

The signal at each step comes from strategies.signal_input, shared with the v2 touch loop.
This is the v1 design (PREREGISTRATION.md, Design history); it stays for the exploratory
GLFT results and the v1 diagnosis.
"""

import numpy as np
from hftbacktest import BUY_EVENT
from numba import njit

from toxic_flow.signals.normalise import Ring
from toxic_flow.strategies.b0_fixed import order_size, sides_allowed
from toxic_flow.strategies.b1_glft import (
    FIT_LEVELS,
    compute_coeff,
    linear_regression,
    measure_trading_intensity,
)
from toxic_flow.strategies.common import both_resting, finish_day, place_quotes, record_fills
from toxic_flow.strategies.signal_input import EWMA, EXTERNAL, HAWKES, NONE, OFI, signal_at

__all__ = ["EWMA", "EXTERNAL", "HAWKES", "NONE", "OFI", "run_b1", "run_overlay"]


@njit(cache=True)
def overlay_ticks(r, half, u, m, c, d, best_bid_tick, best_ask_tick):
    centre = r + c * u * half
    width = half * (1.0 + d * m)
    bid = min(np.floor(centre - width), best_ask_tick - 1)
    ask = max(np.ceil(centre + width), best_bid_tick + 1)
    return bid, ask


@njit
def run_overlay(
    hbt,
    gamma,
    window_steps,
    update_every,
    lot_size,
    min_notional,
    max_lots,
    quote_start_ns,
    quote_end_ns,
    step_ns,
    steps,
    fills,
    out,
    mode,
    c,
    d,
    K,
    norm_steps,
    sig_ts,
    sig_side,
    sig_cum,
    tau_s,
    ofi_window_ns,
    mu,
    alpha,
    beta,
    ext_u,
    ext_m,
    diag,
    touch=False,
):
    """GLFT with an overlay. out as in strategies.b0_fixed.run_b0; diag receives
    (time, u, m) for every step, warm-up included, while it has room."""
    tick = hbt.depth(0).tick_size
    step_s = step_ns / 1e9
    n_max = 2 * 86_400 * 10**9 // step_ns + 10
    arrival = np.full(n_max, np.nan)
    mid_chg = np.full(n_max, np.nan)
    tmp = np.zeros(500)
    ticks = np.arange(len(tmp)) + 0.5
    A, k, sigma, mid_tick = np.nan, np.nan, np.nan, np.nan
    order_qty, next_id, t, n_steps, n_fills, n_diag = 0.0, 1, 0, 0, 0, 0
    a_ring, ofi_ring = Ring(norm_steps), Ring(norm_steps)
    state = np.zeros(4)
    lam = np.empty(2)
    pos = np.zeros(3, np.int64)  # stream positions, see signal_input.signal_at
    while True:
        if hbt.elapse(step_ns) != 0:
            break
        now = hbt.current_timestamp
        if now >= quote_end_ns:
            break
        # GLFT measurement, as in the hftbacktest tutorial (strategies.b1_glft).
        if not np.isnan(mid_tick):
            deepest = -np.inf
            for trade in hbt.last_trades(0):
                p = trade.px / tick
                if trade.ev & BUY_EVENT == BUY_EVENT:
                    deepest = max(p - mid_tick, deepest)
                else:
                    deepest = max(mid_tick - p, deepest)
            arrival[t] = deepest
        hbt.clear_last_trades(0)
        n_fills = record_fills(hbt, fills, n_fills)
        hbt.clear_inactive_orders(0)
        dp = hbt.depth(0)
        bb, ba = dp.best_bid_tick, dp.best_ask_tick
        valid = np.isfinite(dp.best_bid) and np.isfinite(dp.best_ask) and bb < ba
        prev_mid = mid_tick
        mid_tick = (bb + ba) / 2.0 if valid else np.nan
        mid_chg[t] = mid_tick - prev_mid
        if t % update_every == 0 and t >= window_steps - 1:
            tmp[:] = 0
            lam_d = measure_trading_intensity(arrival[t + 1 - window_steps : t + 1], tmp)
            if len(lam_d) > 2:
                lam_d = lam_d[:FIT_LEVELS] / (window_steps * step_s)
                slope, log_a = linear_regression(ticks[: len(lam_d)], np.log(lam_d))
                A, k = np.exp(log_a), -slope
            sigma = np.nanstd(mid_chg[t + 1 - window_steps : t + 1]) * np.sqrt(1.0 / step_s)
        t += 1

        # Signal at now, from inputs received at or before now only.
        u, m = signal_at(
            now, mode, pos, state, lam, a_ring, ofi_ring, K, sig_ts, sig_side, sig_cum,
            tau_s, ofi_window_ns, mu, alpha, beta, ext_u, ext_m,
        )  # fmt: skip
        if n_diag < len(diag):
            diag[n_diag, 0], diag[n_diag, 1], diag[n_diag, 2] = now, u, m
            n_diag += 1
        if now < quote_start_ns:
            continue  # warm-up: estimators and normalisers only, no orders

        position = hbt.position(0)
        both = False
        bid_rec, ask_rec, n_cancel = np.nan, np.nan, 0
        glft_ok = valid and np.isfinite(A) and np.isfinite(k) and np.isfinite(sigma) and k > 0
        if glft_ok or (touch and valid):
            if order_qty == 0.0:
                order_qty = order_size(mid_tick * tick, lot_size, min_notional)
            if touch:
                # Exploratory base (M4 diagnosis, item 5): quotes at the touch, skewed by
                # one tick per order size of inventory, instead of the GLFT price.
                half = 0.5 * (ba - bb)
                r = mid_tick - position / order_qty
            else:
                c1, c2 = compute_coeff(gamma, gamma, 1.0, A, k)
                half = c1 + 0.5 * c2 * sigma
                r = mid_tick - c2 * sigma * (position / order_qty)
            bid_t, ask_t = overlay_ticks(r, half, u, m, c, d, bb, ba)
            want_bid, want_ask = sides_allowed(position, order_qty, max_lots)
            bid_rec = bid_t if want_bid else np.nan
            ask_rec = ask_t if want_ask else np.nan
            both = both_resting(hbt)
            next_id, n_buy, n_sell, n_cancel = place_quotes(
                hbt, int(bid_t), int(ask_t), want_bid, want_ask, order_qty, next_id,
                round(position / order_qty), max_lots,
            )  # fmt: skip
            out[6] = max(out[6], n_buy, n_sell)
            out[7] = max(out[7], abs(round(position / order_qty)))
        else:
            next_id, _, _, n_cancel = place_quotes(
                hbt, 0, 0, False, False, 1.0, next_id, 0, max_lots
            )  # cancel all
        if n_steps < len(steps):
            steps[n_steps].ts = now
            steps[n_steps].mid = mid_tick * tick
            steps[n_steps].position = position
            steps[n_steps].balance = hbt.state_values(0).balance
            steps[n_steps].both_quoted = both
            steps[n_steps].bid_tick, steps[n_steps].ask_tick = bid_rec, ask_rec
            steps[n_steps].best_bid_tick, steps[n_steps].best_ask_tick = bb, ba
            steps[n_steps].cancels = n_cancel
            n_steps += 1
        out[8] = now
    out[0] = n_steps
    out[5] = order_qty
    finish_day(hbt, fills, n_fills, out)


@njit
def run_b1(
    hbt,
    gamma,
    window_steps,
    update_every,
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
    """B1: this loop with no signal and c = d = 0. out as in strategies.b0_fixed.run_b0."""
    empty_i = np.zeros(0, np.int64)
    run_overlay(
        hbt, gamma, window_steps, update_every, lot_size, min_notional, max_lots,
        quote_start_ns, quote_end_ns, step_ns, steps, fills, out,
        NONE, 0.0, 0.0, 1.0, 18_000, empty_i, empty_i, np.zeros(1), 1.0, 1,
        np.zeros(2), np.zeros((2, 2)), 1.0, np.zeros(0), np.zeros(0), np.zeros((0, 3)),
    )  # fmt: skip
