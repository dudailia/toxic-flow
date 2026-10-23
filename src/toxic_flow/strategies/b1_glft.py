"""B1, GLFT market maker (PREREGISTRATION.md section 4): estimation and pricing. The loop
itself is strategies.overlay.run_b1, the overlay loop with no signal.

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
from numba import njit

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
