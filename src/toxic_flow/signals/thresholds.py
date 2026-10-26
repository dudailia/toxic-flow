"""Overlay thresholds from the training days (PREREGISTRATION.md section 5, v2).

theta_u(p) is the (1 - p) quantile of |u| over the training-day decision steps, so the
overlay marks a side toxic (|u| > theta_u) on a share p of those steps. theta_m is the
0.90 quantile of m, so the magnitude rule acts on the top 10%. Like K, both are fixed
numbers computed once from the training days.
"""

import numpy as np

PULL_RATES = (0.05, 0.10, 0.25, 0.50)
MAGNITUDE_Q = 0.90


def theta_u(abs_u: np.ndarray, p: float) -> float:
    return float(np.quantile(abs_u, 1.0 - p))


def theta_m(m: np.ndarray) -> float:
    return float(np.quantile(m, MAGNITUDE_Q))


def share_above(x: np.ndarray, theta: float) -> float:
    """The share of steps where the rule acts: x strictly above theta, as in the loop."""
    return float(np.mean(x > theta))
