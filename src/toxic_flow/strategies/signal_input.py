"""The signal at one decision step, shared by the v1 overlay loop (strategies.overlay) and
the v2 touch loop (strategies.touch), so both compute u and m the same way
(PREREGISTRATION.md section 5).

Inputs are precomputed streams consumed only once their local time is at or before now:
market-order events for EWMA and HAWKES, best-level OFI contributions for OFI. EXTERNAL
takes u and m from a series (time, u, m), again only from points at or before now; the
oracle canary C2 uses it with a series built in tests/canary/ (SPEC.md AC3.6), and the
random-pull control R with a series that reads no market data (engine.run.random_pulls).
The normalisers (Ring) are updated at every 100 ms step from the start of the data, warm-up
included, so they are full when quoting starts.
"""

import numpy as np
from numba import njit

from toxic_flow.signals import ewma, hawkes_online

NONE, OFI, EWMA, HAWKES, EXTERNAL = 0, 1, 2, 3, 4


@njit
def signal_at(
    now, mode, pos, state, lam, a_ring, ofi_ring, K, sig_ts, sig_side, sig_cum,
    tau_s, ofi_window_ns, mu, alpha, beta, ext_u, ext_m,
):  # fmt: skip
    """(u, m) at now. pos holds the stream positions between calls: 0 the next event (or
    series point), 1 and 2 the OFI window's right and left ends. state and lam are the
    EWMA or Hawkes state; a_ring and ofi_ring the trailing normalisers."""
    u, a = 0.0, 0.0
    if mode == EWMA or mode == HAWKES:
        j = pos[0]
        while j < len(sig_ts) and sig_ts[j] <= now:
            if mode == EWMA:
                ewma.step(state, sig_ts[j], sig_side[j], tau_s)
            else:
                hawkes_online.step(state, sig_ts[j], sig_side[j], beta)
            j += 1
        pos[0] = j
        if mode == EWMA:
            u, a = ewma.value(state, now, tau_s)
        else:
            hawkes_online.intensity(state, now, mu, alpha, beta, lam)
            a = lam[0] + lam[1]
            u = (lam[0] - lam[1]) / a
    elif mode == OFI:
        hi, lo = pos[1], pos[2]
        while hi < len(sig_ts) and sig_ts[hi] <= now:
            hi += 1
        while lo < len(sig_ts) and sig_ts[lo] <= now - ofi_window_ns:
            lo += 1
        pos[1], pos[2] = hi, lo
        ofi = sig_cum[hi] - sig_cum[lo]
        ofi_ring.push(ofi)
        s = ofi_ring.std()
        u = np.tanh(ofi / s) if s > 0 else 0.0
        a = abs(ofi)
    if mode == EXTERNAL:
        j = pos[0]
        while j < len(sig_ts) and sig_ts[j] <= now:
            j += 1
        pos[0] = j
        return (ext_u[j - 1], ext_m[j - 1]) if j > 0 else (0.0, 0.0)
    a_ring.push(a)
    abar = a_ring.mean()
    m = min(max((a / abar - 1.0) / K, 0.0), 1.0) if abar > 0 else 0.0
    return u, m
