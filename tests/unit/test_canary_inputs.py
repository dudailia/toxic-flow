"""Inputs of canaries C1 and C4 (PREREGISTRATION.md section 10)."""

import numpy as np
import pytest

from toxic_flow.engine.run import shuffled_sides
from toxic_flow.signals.hawkes_fit import branching_ratio, rescale_decay

P = {"mu_b": 1.3, "mu_s": 1.4, "alpha_bb": 4.3, "alpha_bs": 0.4, "alpha_sb": 0.3,
     "alpha_ss": 4.3, "beta": 7.8}  # fmt: skip


def alpha(p):
    return np.array([[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]])


@pytest.mark.parametrize("factor", [10.0, 0.1])
def test_c4_rescales_decay_and_keeps_the_branching_ratio(factor):
    q = rescale_decay(P, factor)
    assert q["beta"] == pytest.approx(P["beta"] * factor)
    assert branching_ratio(alpha(q), q["beta"]) == pytest.approx(
        branching_ratio(alpha(P), P["beta"])
    )
    assert (q["mu_b"], q["mu_s"]) == (P["mu_b"], P["mu_s"])


def test_c1_permutes_sides_within_the_day_with_a_fixed_seed():
    side = np.array([0] * 70 + [1] * 30)
    a, b = shuffled_sides(side, seed=1729), shuffled_sides(side, seed=1729)
    assert np.array_equal(a, b) and a.sum() == 30 and not np.array_equal(a, side)
