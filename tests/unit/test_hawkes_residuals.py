"""Time-rescaling residuals (SPEC.md AC3.5): under the right model, each type's compensator
increments between its own events are i.i.d. Exp(1)."""

import numpy as np
import pytest

from toxic_flow.signals.hawkes_fit import rescaled_residuals, residual_report
from toxic_flow.signals.hawkes_sim import simulate

MU = np.array([0.6, 0.4])
ALPHA = np.array([[0.8, 0.3], [0.2, 0.7]])
BETA = 2.0


def direct_compensator(t, times, types, k, mu, alpha, beta):
    past = times < t
    return mu[k] * t + sum(
        alpha[k, j] / beta * (1 - np.exp(-beta * (t - times[past & (types == j)]))).sum()
        for j in (0, 1)
    )


def test_residuals_match_the_compensator_definition():
    times, types = simulate(MU, ALPHA, BETA, T=60.0, seed=4)
    res = rescaled_residuals(times, types, MU, ALPHA, BETA)
    for k in (0, 1):
        own = times[types == k]
        lam = [direct_compensator(t, times, types, k, MU, ALPHA, BETA) for t in own]
        np.testing.assert_allclose(res[k], np.diff(np.concatenate([[0.0], lam])), rtol=1e-10)


def test_true_parameters_give_exponential_residuals():
    times, types = simulate(MU, ALPHA, BETA, T=5000.0, seed=8)
    rep = residual_report(times, types, MU, ALPHA, BETA)
    for k in ("b", "s"):
        assert rep[k]["mean"] == pytest.approx(1.0, abs=0.03)
        assert rep[k]["ks_pvalue"] > 0.01


def test_a_wrong_decay_is_rejected():
    times, types = simulate(MU, ALPHA, BETA, T=5000.0, seed=8)
    rep = residual_report(times, types, MU, ALPHA * 10 / 10, BETA * 10)  # decay ten times too fast
    assert min(rep["b"]["ks_pvalue"], rep["s"]["ks_pvalue"]) < 1e-6
