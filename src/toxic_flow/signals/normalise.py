"""Trailing normalisers and the constant K (PREREGISTRATION.md section 5).

    m(t) = clip((a(t) / abar(t) - 1) / K, 0, 1)

abar is the trailing 30-minute mean of a at decision steps; K is the 99th percentile of
a / abar - 1 on training days for that signal and parameter. Trailing windows keep every
value causal. Ring is the online form used inside the strategy loops.
"""

import numpy as np
from numba import float64, int64
from numba.experimental import jitclass

NORM_STEPS = 18_000  # 30 minutes of 100 ms decision steps


def trailing_mean(x: np.ndarray, n: int) -> np.ndarray:
    """Mean of the last n values up to and including each one; NaN until n values exist."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1 :] = (c[n:] - c[:-n]) / n
    return out


def k_constant(a: np.ndarray, abar: np.ndarray, q: float = 99.0) -> float:
    ok = np.isfinite(abar) & (abar > 0)
    return float(np.percentile(a[ok] / abar[ok] - 1.0, q))


def magnitude(a: np.ndarray, abar: np.ndarray, K: float) -> np.ndarray:
    """m in [0, 1]; 0 while abar is unknown or zero."""
    out = np.zeros(len(a))
    ok = np.isfinite(abar) & (abar > 0)
    out[ok] = np.clip((a[ok] / abar[ok] - 1.0) / K, 0.0, 1.0)
    return out


@jitclass(
    [
        ("buf", float64[:]),
        ("n", int64),
        ("i", int64),
        ("count", int64),
        ("s1", float64),
        ("s2", float64),
    ]
)
class Ring:
    """The last n values with their mean and population standard deviation, O(1) per push.
    Running sums are recomputed exactly each time the buffer wraps, so float error cannot
    build up over a day."""

    def __init__(self, n):
        self.buf = np.zeros(n)
        self.n, self.i, self.count, self.s1, self.s2 = n, 0, 0, 0.0, 0.0

    def push(self, x):
        if self.count == self.n:
            old = self.buf[self.i]
            self.s1 -= old
            self.s2 -= old * old
        else:
            self.count += 1
        self.buf[self.i] = x
        self.s1 += x
        self.s2 += x * x
        self.i = (self.i + 1) % self.n
        if self.i == 0:
            self.s1 = np.sum(self.buf)
            self.s2 = np.sum(self.buf * self.buf)

    def mean(self):
        return self.s1 / self.n if self.count == self.n else np.nan

    def std(self):
        if self.count < self.n:
            return np.nan
        v = self.s2 / self.n - (self.s1 / self.n) ** 2
        return np.sqrt(v) if v > 0 else 0.0
