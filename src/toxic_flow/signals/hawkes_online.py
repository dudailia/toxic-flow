"""Hawkes intensity at decision times, updated in O(1) per event (SPEC.md M3).

At decision time t the intensity uses every event with local_ts <= t
(PREREGISTRATION.md section 5), and nothing later. Times are int64 nanoseconds; mu and
beta are per second, as fitted by hawkes_fit.
"""

import numpy as np
from numba import njit


@njit(cache=True)
def step(state, t_ns, k, beta):
    """Add an event of type k at t_ns. state = [R_b, R_s, last event time, any event yet]."""
    if state[3] != 0.0:
        decay = np.exp(-beta * (t_ns - state[2]) / 1e9)
        state[0] *= decay
        state[1] *= decay
    state[2] = t_ns
    state[3] = 1.0
    state[k] += 1.0


@njit(cache=True)
def intensity(state, t_ns, mu, alpha, beta, out):
    """lambda_b and lambda_s at t_ns >= the last event, into out[0], out[1]."""
    decay = np.exp(-beta * (t_ns - state[2]) / 1e9) if state[3] != 0.0 else 0.0
    r0, r1 = state[0] * decay, state[1] * decay
    out[0] = mu[0] + alpha[0, 0] * r0 + alpha[0, 1] * r1
    out[1] = mu[1] + alpha[1, 0] * r0 + alpha[1, 1] * r1


@njit(cache=True)
def hawkes_at(event_ts, event_type, decision_ts, mu, alpha, beta):
    """Intensities (m, 2) at sorted decision times from sorted events, in one pass."""
    out = np.empty((len(decision_ts), 2))
    state = np.zeros(4)
    lam = np.empty(2)
    i = 0
    for d in range(len(decision_ts)):
        t = decision_ts[d]
        while i < len(event_ts) and event_ts[i] <= t:
            step(state, event_ts[i], event_type[i], beta)
            i += 1
        intensity(state, t, mu, alpha, beta, lam)
        out[d, 0], out[d, 1] = lam[0], lam[1]
    return out


def hawkes_signal(event_ts, event_type, decision_ts, mu, alpha, beta):
    """Direction u and activity a (PREREGISTRATION.md section 5) at each decision time."""
    lam = hawkes_at(event_ts, event_type, decision_ts, np.asarray(mu), np.asarray(alpha), beta)
    a = lam[:, 0] + lam[:, 1]
    return (lam[:, 0] - lam[:, 1]) / a, a
