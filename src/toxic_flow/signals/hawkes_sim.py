"""Simulate the bivariate exponential Hawkes process by Ogata thinning (for tests and
canaries; never fed real data)."""

import numpy as np


def simulate(mu, alpha, beta, T: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Event times (seconds in [0, T]) and types (0 b, 1 s).

    Between events every intensity only decays, so the total intensity just after the
    last event bounds it until the next one: propose from that bound, accept with the
    ratio of the true total intensity to it, and pick the type in proportion.
    """
    mu, alpha = np.asarray(mu, float), np.asarray(alpha, float)
    rng = np.random.default_rng(seed)
    t, r = 0.0, np.zeros(2)
    times, types = [], []
    while True:
        bound = mu.sum() + alpha.sum(axis=0) @ r
        w = rng.exponential(1.0 / bound)
        t += w
        if t > T:
            break
        r *= np.exp(-beta * w)
        lam = mu + alpha @ r
        u = rng.uniform() * bound
        if u <= lam.sum():
            k = 0 if u <= lam[0] else 1
            times.append(t)
            types.append(k)
            r[k] += 1.0
    return np.array(times), np.array(types, np.int64)
