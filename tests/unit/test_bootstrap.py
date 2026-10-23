"""Analysis (PREREGISTRATION.md sections 8, 9 and 11) on made-up day-level numbers."""

import numpy as np
import pytest
from scipy import stats

from toxic_flow.eval.bootstrap import (
    bootstrap_ci,
    conclusion,
    mde,
    paired_differences,
    selectivity,
    t_interval,
)


def test_paired_differences_drop_and_report_days_with_zero_fills():
    a = {"d1": (1.0, 10), "d2": (2.0, 0), "d3": (3.0, 5)}  # (BEF, fills)
    b = {"d1": (0.5, 10), "d2": (1.0, 7), "d3": (1.0, 5)}
    days, d, dropped = paired_differences(a, b)
    assert days == ["d1", "d3"] and list(d) == [0.5, 2.0] and dropped == ["d2"]


def test_bootstrap_is_reproducible_with_seed_1729_and_brackets_the_mean():
    d = np.random.default_rng(0).normal(0.2, 1.0, 16)
    lo, hi = bootstrap_ci(d)
    assert (lo, hi) == bootstrap_ci(d)
    assert lo < d.mean() < hi
    means = d[np.random.default_rng(1729).integers(0, 16, (10_000, 16))].mean(axis=1)
    assert (lo, hi) == tuple(np.percentile(means, [2.5, 97.5]))


def test_t_interval_matches_scipy():
    d = np.array([0.1, -0.2, 0.4, 0.3, 0.0, 0.5])
    lo, hi = t_interval(d)
    half = stats.t.ppf(0.975, 5) * d.std(ddof=1) / np.sqrt(6)
    assert lo == pytest.approx(d.mean() - half) and hi == pytest.approx(d.mean() + half)


def test_mde_is_2_80_s_over_root_n():
    assert mde(1.0, 16) == pytest.approx((stats.norm.ppf(0.975) + stats.norm.ppf(0.8)) / 4)
    assert mde(1.0, 16) == pytest.approx(0.70, abs=0.001)


@pytest.mark.parametrize(
    "boot, t, signs, mean, m, key",
    [
        ((0.1, 0.5), (0.05, 0.6), [1] * 8, 0.3, 0.2, "holds_positive"),
        ((-0.5, -0.1), (-0.6, -0.05), [-1] * 8, -0.3, 0.2, "holds_negative"),
        ((0.1, 0.5), (0.05, 0.6), [1] * 7 + [-1], 0.3, 0.2, "does_not_hold"),
        ((-0.1, 0.3), (-0.2, 0.4), [1] * 8, 0.1, 0.2, "no_detectable_difference"),
        ((-0.1, 0.9), (-0.2, 1.0), [1] * 8, 0.4, 0.2, "inconclusive"),
        ((0.01, 0.5), (-0.05, 0.6), [1] * 8, 0.3, 0.2, "inconclusive"),  # intervals disagree
        # They disagree with |mean| below the MDE: section 11's "large" sentence would be false.
        ((0.01, 0.2), (-0.01, 0.21), [1] * 8, 0.1, 0.5, "intervals_disagree"),
    ],
)
def test_pre_committed_conclusions(boot, t, signs, mean, m, key):
    assert conclusion(boot, t, mean, signs, m)["key"] == key


def test_selectivity_flags_a_strategy_that_trades_under_half():
    assert selectivity([100.0, 40.0, 30.0], [100.0, 100.0, 100.0])["flag"]
    assert not selectivity([90.0, 80.0, 70.0], [100.0, 100.0, 100.0])["flag"]
