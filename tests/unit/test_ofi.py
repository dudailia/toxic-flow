"""B2 signal: best-level order-flow imbalance (Cont, Kukanov and Stoikov 2014)."""

import numpy as np
import pytest

from toxic_flow.data.book import BBO_DTYPE
from toxic_flow.signals.ofi import ofi_contributions, ofi_signal, ofi_window, trailing_std

S = 10**9


def bbo(rows):
    out = np.zeros(len(rows), BBO_DTYPE)
    for i, r in enumerate(rows):
        out[i] = r
    return out


def test_contributions_follow_the_definition():
    rows = bbo(
        [
            (0 * S, 100.0, 5.0, 100.1, 4.0),
            (1 * S, 100.0, 7.0, 100.1, 4.0),  # bid queue +2 at the same price: +2
            (2 * S, 100.05, 1.0, 100.1, 4.0),  # bid price up: + new bid qty 1
            (3 * S, 100.05, 1.0, 100.1, 6.0),  # ask queue +2 at the same price: -2
            (4 * S, 100.05, 1.0, 100.08, 3.0),  # ask price down: - new ask qty 3
            (5 * S, 100.0, 9.0, 100.08, 3.0),  # bid price down: - old bid qty 1
        ]
    )
    ts, e = ofi_contributions(rows)
    assert list(ts) == [1 * S, 2 * S, 3 * S, 4 * S, 5 * S]
    np.testing.assert_allclose(e, [2.0, 1.0, -2.0, -3.0, -1.0])


def test_window_sums_updates_in_t_minus_w_to_t():
    ts = np.array([1, 2, 3, 4], np.int64) * S
    e = np.array([1.0, 10.0, 100.0, 1000.0])
    out = ofi_window(ts, e, np.array([3 * S, 4 * S, 10 * S], np.int64), 2.0)
    np.testing.assert_allclose(out, [110.0, 1100.0, 0.0])  # (1, 3] and (2, 4]


def test_trailing_std_uses_only_the_last_n_values():
    x = np.array([1.0, 2.0, 3.0, 10.0, 10.0])
    s = trailing_std(x, 3)
    assert np.isnan(s[0])
    assert s[2] == pytest.approx(np.std([1, 2, 3]))
    assert s[4] == pytest.approx(np.std([3, 10, 10]))


def test_signal_u_is_tanh_of_the_normalised_window():
    rows = bbo([(i * S, 100.0, 1.0 + (i % 3), 100.1, 2.0) for i in range(50)])
    decisions = np.arange(5, 50, dtype=np.int64) * S
    u, a, ofi = ofi_signal(rows, decisions, window_s=2.0, norm_steps=10)
    s = trailing_std(ofi, 10)
    ok = s > 0
    np.testing.assert_allclose(u[ok], np.tanh(ofi[ok] / s[ok]))
    assert np.all(u[~ok] == 0.0)
    np.testing.assert_allclose(a, np.abs(ofi))
