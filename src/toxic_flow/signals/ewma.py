"""B2b signal: signed decay-weighted counts of market-order events (PREREGISTRATION.md 5).

    E_b(t) = sum over buy events with local_ts <= t of exp(-(t - local_ts) / tau)
    u = (E_b - E_s) / (E_b + E_s), 0 when both are 0;  a = E_b + E_s

step and value are shared by the offline function and the strategy loop, so both compute
the signal the same way.
"""

import numpy as np
from numba import njit


@njit(cache=True)
def step(state, t_ns, side, tau_s):
    """Add an event (side 0 buy, 1 sell). state = [E_b, E_s, last event time, any yet]."""
    if state[3] != 0.0:
        decay = np.exp(-(t_ns - state[2]) / 1e9 / tau_s)
        state[0] *= decay
        state[1] *= decay
    state[2] = t_ns
    state[3] = 1.0
    state[side] += 1.0


@njit(cache=True)
def value(state, t_ns, tau_s):
    """(u, a) at t_ns at or after the last event."""
    if state[3] == 0.0:
        return 0.0, 0.0
    decay = np.exp(-(t_ns - state[2]) / 1e9 / tau_s)
    b, s = state[0] * decay, state[1] * decay
    return ((b - s) / (b + s) if b + s > 0 else 0.0), b + s


@njit(cache=True)
def ewma_at(event_ts, event_side, decision_ts, tau_s):
    """(u, a) at sorted decision times (int64 ns) from sorted events; side 0 buy, 1 sell."""
    u = np.zeros(len(decision_ts))
    a = np.zeros(len(decision_ts))
    state = np.zeros(4)
    i = 0
    for d in range(len(decision_ts)):
        t = decision_ts[d]
        while i < len(event_ts) and event_ts[i] <= t:
            step(state, event_ts[i], event_side[i], tau_s)
            i += 1
        u[d], a[d] = value(state, t, tau_s)
    return u, a
