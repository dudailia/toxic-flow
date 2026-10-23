"""B1, GLFT (PREREGISTRATION.md section 4; formulas from the hftbacktest GLFT tutorial)."""

import numpy as np
import pytest

from toxic_flow.strategies.b1_glft import compute_coeff, glft_ticks, linear_regression


def test_compute_coeff_matches_the_tutorial_formula():
    xi, gamma, delta, A, k = 0.05, 0.05, 1.0, 2.0, 0.8
    c1, c2 = compute_coeff(xi, gamma, delta, A, k)
    assert c1 == pytest.approx(1 / (xi * delta) * np.log(1 + xi * delta / k))
    assert c2 == pytest.approx(
        np.sqrt(gamma / (2 * A * delta * k) * (1 + xi * delta / k) ** (k / (xi * delta) + 1))
    )


def test_linear_regression_recovers_a_line():
    x = np.arange(10.0)
    slope, intercept = linear_regression(x, 3.0 - 0.5 * x)
    assert slope == pytest.approx(-0.5) and intercept == pytest.approx(3.0)


def test_quotes_round_outward_and_skew_against_inventory():
    flat = glft_ticks(1000.5, 0.0, 2.0, 0.8, 1.0, 0.05, 1000, 1001)
    long = glft_ticks(1000.5, 5.0, 2.0, 0.8, 1.0, 0.05, 1000, 1001)
    bid, ask, half, skew = flat
    assert bid == np.floor(1000.5 - half) and ask == np.ceil(1000.5 + half)
    assert long[0] < bid and long[1] < ask  # long inventory lowers both quotes
    assert skew > 0


def test_quotes_never_cross_the_book():
    # Large short inventory pushes the reservation price far above the ask.
    bid, ask, _, _ = glft_ticks(1000.5, -500.0, 2.0, 0.8, 1.0, 0.05, 1000, 1001)
    assert bid == 1000 and ask > 1000  # bid moved to best ask - 1 tick
