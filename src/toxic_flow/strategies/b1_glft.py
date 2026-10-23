"""B1, GLFT market maker (PREREGISTRATION.md section 4), as a numba loop over hftbacktest.

The estimation follows the hftbacktest GLFT tutorial ("GLFT Market Making Model and Grid
Trading", examples/ at tag py-v2.4.4): each 100 ms step records the deepest market-order
arrival from the previous mid; every update_every steps A and k are fitted to
lambda(depth) = A exp(-k depth) over the trailing window, and the volatility is the
standard deviation of mid changes over the window, per square-root second, in ticks.
Then, with xi = gamma and delta = 1 order size:

    half spread = c1 + delta / 2 * c2 * sigma,  skew = c2 * sigma,  r = mid - skew * q

where q is inventory in order sizes. Two departures from the tutorial, both required by
PREREGISTRATION.md section 4: quotes round outward (bid down, ask up) instead of to the
nearest tick and are not capped at the best price, and a bid at or above the best ask
moves to one tick below it (and the mirror for asks).
"""

import numpy as np
from hftbacktest import BUY_EVENT
from numba import njit

from toxic_flow.strategies.b0_fixed import order_size, sides_allowed
from toxic_flow.strategies.common import finish_day, place_quotes, record_fills

FIT_LEVELS = 70  # depth levels used in the intensity fit, as in the tutorial


@njit(cache=True)
def measure_trading_intensity(order_arrival_depth, out):
    """Tutorial code: count, for each depth level in ticks from the nearest quote, how many
    steps had a market order reach at least that far."""
    max_tick = 0
    for depth in order_arrival_depth:
        if not np.isfinite(depth):
            continue
        tick = round(depth / 0.5) - 1  # index 0 is the nearest possible quote, half a tick out
        if tick < 0 or tick >= len(out):
            continue
        out[:tick] += 1
        max_tick = max(max_tick, tick)
    return out[:max_tick]


@njit(cache=True)
def linear_regression(x, y):
    sx, sy = np.sum(x), np.sum(y)
    sx2, sxy = np.sum(x**2), np.sum(x * y)
    w = len(x)
    slope = (w * sxy - sx * sy) / (w * sx2 - sx**2)
    return slope, (sy - slope * sx) / w


@njit(cache=True)
def compute_coeff(xi, gamma, delta, A, k):
    inv_k = np.divide(1, k)
    c1 = 1 / (xi * delta) * np.log(1 + xi * delta * inv_k)
    c2 = np.sqrt(
        np.divide(gamma, 2 * A * delta * k) * ((1 + xi * delta * inv_k) ** (k / (xi * delta) + 1))
    )
    return c1, c2


@njit(cache=True)
def glft_ticks(mid_tick, q, A, k, sigma, gamma, best_bid_tick, best_ask_tick):
    """(bid tick, ask tick, half spread, skew) in ticks."""
    c1, c2 = compute_coeff(gamma, gamma, 1.0, A, k)
    half = c1 + 0.5 * c2 * sigma
    skew = c2 * sigma
    r = mid_tick - skew * q
    bid = min(np.floor(r - half), best_ask_tick - 1)
    ask = max(np.ceil(r + half), best_bid_tick + 1)
    return bid, ask, half, skew


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
    """Measure from the first step, quote from quote_start_ns until quote_end_ns.

    steps receives one row per quoting step, fills one row per fill. out: 0 steps quoted,
    1 fills (engine), 2 position, 3 cash, 4 mark mid, 5 order size, 6 most orders on one
    side, 7 largest inventory in order sizes, 8 last decision time, 9 mark time, 10 fee,
    11 traded value, 12 fills recorded.
    """
    tick = hbt.depth(0).tick_size
    step_s = step_ns / 1e9
    n_max = 2 * 86_400 * 10**9 // step_ns + 10  # longer than any day of steps
    arrival = np.full(n_max, np.nan)
    mid_chg = np.full(n_max, np.nan)
    tmp = np.zeros(500)
    ticks = np.arange(len(tmp)) + 0.5
    A, k, sigma = np.nan, np.nan, np.nan
    mid_tick = np.nan
    order_qty, next_id, t, n_steps, n_fills = 0.0, 1, 0, 0, 0
    while True:
        if hbt.elapse(step_ns) != 0:
            break
        now = hbt.current_timestamp
        if now >= quote_end_ns:
            break
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
        d = hbt.depth(0)
        bb, ba = d.best_bid_tick, d.best_ask_tick
        valid = np.isfinite(d.best_bid) and np.isfinite(d.best_ask) and bb < ba
        prev_mid = mid_tick
        mid_tick = (bb + ba) / 2.0 if valid else np.nan
        mid_chg[t] = mid_tick - prev_mid
        if t % update_every == 0 and t >= window_steps - 1:
            tmp[:] = 0
            lam = measure_trading_intensity(arrival[t + 1 - window_steps : t + 1], tmp)
            if len(lam) > 2:
                lam = lam[:FIT_LEVELS] / (window_steps * step_s)
                slope, log_a = linear_regression(ticks[: len(lam)], np.log(lam))
                A, k = np.exp(log_a), -slope
            sigma = np.nanstd(mid_chg[t + 1 - window_steps : t + 1]) * np.sqrt(1.0 / step_s)
        t += 1
        if now < quote_start_ns:
            continue  # warm-up: estimators only, no orders

        position = hbt.position(0)
        both = False
        if valid and np.isfinite(A) and np.isfinite(k) and np.isfinite(sigma) and k > 0:
            if order_qty == 0.0:
                order_qty = order_size(mid_tick * tick, lot_size, min_notional)
            bid_t, ask_t, _, _ = glft_ticks(
                mid_tick, position / order_qty, A, k, sigma, gamma, bb, ba
            )
            want_bid, want_ask = sides_allowed(position, order_qty, max_lots)
            next_id, n_buy, n_sell = place_quotes(
                hbt, int(bid_t), int(ask_t), want_bid, want_ask, order_qty, next_id
            )
            both = (n_buy > 0 or want_bid) and (n_sell > 0 or want_ask)
            out[6] = max(out[6], n_buy, n_sell)
            out[7] = max(out[7], abs(round(position / order_qty)))
        else:
            next_id, _, _ = place_quotes(hbt, 0, 0, False, False, 1.0, next_id)  # cancel all
        if n_steps < len(steps):
            steps[n_steps].ts = now
            steps[n_steps].mid = mid_tick * tick
            steps[n_steps].position = position
            steps[n_steps].balance = hbt.state_values(0).balance
            steps[n_steps].both_quoted = both
            n_steps += 1
        out[8] = now
    out[0] = n_steps
    out[5] = order_qty
    finish_day(hbt, fills, n_fills, out)
