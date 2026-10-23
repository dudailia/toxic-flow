"""B2b signal: signed decay-weighted counts of market-order events (PREREGISTRATION.md 5).

E_b(t) = sum over buy events with local_ts <= t of exp(-(t - local_ts) / tau)
u = (E_b - E_s) / (E_b + E_s), 0 when both are 0;  a = E_b + E_s
"""

import numpy as np
from numba import njit


@njit(cache=True)
def ewma_at(event_ts, event_side, decision_ts, tau_s):
    """(u, a) at sorted decision times (int64 ns) from sorted events; side 0 buy, 1 sell."""
    u = np.zeros(len(decision_ts))
    a = np.zeros(len(decision_ts))
    e0, e1, last = 0.0, 0.0, 0
    seen = False
    i = 0
    for d in range(len(decision_ts)):
        t = decision_ts[d]
        while i < len(event_ts) and event_ts[i] <= t:
            if seen:
                decay = np.exp(-(event_ts[i] - last) / 1e9 / tau_s)
                e0 *= decay
                e1 *= decay
            last, seen = event_ts[i], True
            if event_side[i] == 0:
                e0 += 1.0
            else:
                e1 += 1.0
            i += 1
        if seen:
            decay = np.exp(-(t - last) / 1e9 / tau_s)
            b, s = e0 * decay, e1 * decay
            a[d] = b + s
            u[d] = (b - s) / (b + s) if b + s > 0 else 0.0
    return u, a
