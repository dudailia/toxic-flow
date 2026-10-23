"""Hawkes likelihood, fit, simulator and online intensity (SPEC.md M3, AC3.2 and AC3.3)."""

import numpy as np
import pytest

from toxic_flow.signals.hawkes_fit import branching_ratio, fit, loglik
from toxic_flow.signals.hawkes_online import hawkes_at
from toxic_flow.signals.hawkes_sim import simulate

MU = np.array([0.6, 0.4])
ALPHA = np.array([[0.8, 0.3], [0.2, 0.7]])  # alpha[k, j]: effect of a type-j event on k
BETA = 2.0


def direct_loglik(times, types, T, mu, alpha, beta):
    """The definition, O(n^2): sum of log intensities minus the compensator."""
    ll = 0.0
    for t, k in zip(times, types, strict=True):
        past = times < t  # strictly earlier: events at the same instant do not excite
        lam = mu[k] + sum(
            alpha[k, j] * np.exp(-beta * (t - times[past & (types == j)])).sum() for j in (0, 1)
        )
        ll += np.log(lam)
    comp = mu.sum() * T
    for j in (0, 1):
        comp += alpha[:, j].sum() / beta * (1 - np.exp(-beta * (T - times[types == j]))).sum()
    return ll - comp


def test_recursive_loglik_equals_the_direct_sum_with_ties():
    rng = np.random.default_rng(3)
    times = np.sort(np.round(rng.uniform(0, 50, 300), 1))  # rounding makes ties
    types = rng.integers(0, 2, 300)
    ours = loglik(times, types, 50.0, MU, ALPHA, BETA)
    assert ours == pytest.approx(direct_loglik(times, types, 50.0, MU, ALPHA, BETA), rel=1e-10)


def test_branching_ratio_is_the_spectral_radius_of_alpha_over_beta():
    assert branching_ratio(ALPHA, BETA) == pytest.approx(max(abs(np.linalg.eigvals(ALPHA / BETA))))


def test_simulated_rate_matches_the_stationary_rate():
    times, types = simulate(MU, ALPHA, BETA, T=4000.0, seed=11)
    stationary = np.linalg.solve(np.eye(2) - ALPHA / BETA, MU)
    for k in (0, 1):
        assert (types == k).sum() / 4000.0 == pytest.approx(stationary[k], rel=0.06)
    assert np.all(np.diff(times) >= 0)


def test_ac3_2_online_intensity_equals_the_offline_formula():
    times, types = simulate(MU, ALPHA, BETA, T=300.0, seed=5)
    ts = (times * 1e9).astype(np.int64)
    decisions = np.arange(0, 300 * 10**9, 100_000_000, dtype=np.int64)
    online = hawkes_at(ts, types, decisions, MU, ALPHA, BETA)
    for d in decisions[::37]:
        past = ts <= d  # PREREGISTRATION.md section 5: events with local_ts <= t
        lag = (d - ts[past]) / 1e9
        offline = MU + np.array(
            [
                sum(ALPHA[k, j] * np.exp(-BETA * lag[types[past] == j]).sum() for j in (0, 1))
                for k in (0, 1)
            ]
        )
        np.testing.assert_allclose(online[decisions == d][0], offline, rtol=1e-9)


@pytest.mark.slow
def test_ac3_3_fit_recovers_each_parameter_within_three_standard_errors():
    days = []
    for seed in range(4):  # pooled like training days: four independent realisations
        times, types = simulate(MU, ALPHA, BETA, T=7000.0, seed=100 + seed)
        days.append((times, types, 7000.0))
    n = sum(len(t) for t, _, _ in days)
    assert n >= 50_000
    res = fit(days)
    truth = dict(
        zip(
            ["mu_b", "mu_s", "alpha_bb", "alpha_bs", "alpha_sb", "alpha_ss", "beta"],
            [*MU, *ALPHA.ravel(), BETA],
            strict=True,
        )
    )
    for name, value in truth.items():
        assert abs(res["params"][name] - value) < 3 * res["se"][name], (
            name,
            res["params"][name],
            value,
        )
    assert res["branching_ratio"] < 1


def test_an_event_at_time_zero_still_decays():
    lam = hawkes_at(
        np.array([0], np.int64), np.array([0]), np.array([10**9], np.int64), MU, ALPHA, BETA
    )
    assert lam[0, 0] == pytest.approx(MU[0] + ALPHA[0, 0] * np.exp(-BETA))
