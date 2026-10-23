import numpy as np
import pytest

from toxic_flow.signals.ewma import ewma_at

S = 10**9


def test_ewma_counts_decay_with_tau_and_include_events_at_t():
    ts = np.array([0, 1 * S, 1 * S], np.int64)
    side = np.array([0, 0, 1])  # 0 buy, 1 sell
    u, a = ewma_at(ts, side, np.array([1 * S, 3 * S], np.int64), tau_s=2.0)
    e_b = np.exp(-0.5) + 1.0  # at t = 1 s: the event at 0 has decayed by exp(-1/2)
    assert a[0] == pytest.approx(e_b + 1.0)
    assert u[0] == pytest.approx((e_b - 1.0) / (e_b + 1.0))
    assert a[1] == pytest.approx(a[0] * np.exp(-1.0))  # two seconds later


def test_ewma_is_zero_before_any_event():
    u, a = ewma_at(np.array([5 * S], np.int64), np.array([1]), np.array([1 * S], np.int64), 1.0)
    assert u[0] == 0.0 and a[0] == 0.0
