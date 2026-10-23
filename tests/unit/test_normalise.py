"""Trailing normalisers and the constant K (PREREGISTRATION.md section 5)."""

import numpy as np
import pytest

from toxic_flow.signals.normalise import Ring, k_constant, magnitude, trailing_mean


def test_trailing_mean_uses_the_last_n_values_and_is_nan_before():
    m = trailing_mean(np.array([1.0, 2.0, 3.0, 10.0]), 2)
    assert np.isnan(m[0]) and m[1] == 1.5 and m[3] == 6.5


def test_k_is_the_99th_percentile_of_a_over_abar_minus_one():
    a = np.arange(1, 1001, dtype=float)
    abar = np.full(1000, 100.0)
    assert k_constant(a, abar) == pytest.approx(np.percentile(a / abar - 1, 99))


def test_magnitude_is_clipped_to_zero_one_and_zero_while_abar_is_unknown():
    a = np.array([5.0, 100.0, 150.0, 400.0, 50.0])
    abar = np.array([np.nan, 100.0, 100.0, 100.0, 100.0])
    np.testing.assert_allclose(magnitude(a, abar, K=2.0), [0.0, 0.0, 0.25, 1.0, 0.0])


def test_online_ring_matches_the_offline_trailing_statistics():
    rng = np.random.default_rng(0)
    x = rng.normal(5, 2, 500)
    ring = Ring(50)
    means, stds = [], []
    for v in x:
        ring.push(v)
        means.append(ring.mean())
        stds.append(ring.std())
    from toxic_flow.signals.ofi import trailing_std

    np.testing.assert_allclose(np.array(means)[49:], trailing_mean(x, 50)[49:], rtol=1e-9)
    np.testing.assert_allclose(np.array(stds)[49:], trailing_std(x, 50)[49:], rtol=1e-9)
    assert np.isnan(means[48]) and np.isnan(stds[48])
