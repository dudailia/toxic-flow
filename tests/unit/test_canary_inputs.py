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


def test_r_pulls_a_random_side_at_the_given_rate_with_a_fixed_seed():
    from toxic_flow.engine.run import random_pulls

    start, end, step = 10**12, 10**12 + 3600 * 10**9, 100_000_000
    ts, u, m = random_pulls("2025-01-01", start, end, step, 0.05, seed=1)
    assert ts[0] < start <= ts[1] and ts[-1] >= end - step and np.all(np.diff(ts) == step)
    assert set(np.unique(u)) <= {-1.0, 0.0, 1.0} and not m.any()
    assert abs((u != 0).mean() - 0.05) < 0.003
    assert abs((u == 1).sum() / (u != 0).sum() - 0.5) < 0.03
    again = random_pulls("2025-01-01", start, end, step, 0.05, seed=1)[1]
    other_seed = random_pulls("2025-01-01", start, end, step, 0.05, seed=2)[1]
    other_day = random_pulls("2025-02-01", start, end, step, 0.05, seed=1)[1]
    assert np.array_equal(u, again)
    assert not np.array_equal(u, other_seed) and not np.array_equal(u, other_day)


def test_r_runs_as_b1_pulling_on_its_series_at_the_days_rate():
    from toxic_flow.engine.run import _touch_args, random_pulls, utc_ns
    from toxic_flow.strategies.signal_input import EXTERNAL
    from toxic_flow.strategies.touch import PULL

    cfg = {"quote_start": "00:30:00", "quote_end": "23:59:00", "step_ns": 100_000_000}
    s = {"name": "R", "design": "v2", "seed": 2, "k_ticks": "pull",
         "pull_rate": {"2025-01-01": 0.01, "2025-02-01": 0.3}}  # fmt: skip
    args = _touch_args(s, "2025-02-01", cfg)
    skew, mode, ts, u = args[0], args[1], args[4], args[12]
    theta_u, k_ticks, theta_m = args[14], args[15], args[16]
    want = random_pulls("2025-02-01", utc_ns("2025-02-01", "00:30:00"),
                        utc_ns("2025-02-01", "23:59:00"), 100_000_000, 0.3, 2)  # fmt: skip
    assert skew and mode == EXTERNAL and np.array_equal(ts, want[0])
    assert np.array_equal(u, want[1])
    assert (theta_u, k_ticks, theta_m) == (0.5, PULL, np.inf)


def test_rl_matches_the_rate_and_the_number_of_pulled_runs():
    from toxic_flow.engine.run import random_pulls, run_length_pulls
    from toxic_flow.eval.metrics import toxic_episodes

    start, end, step = 10**12, 10**12 + 24 * 3600 * 10**9, 100_000_000
    rate, runs = 0.25, 8000  # about B2b on a validation day: runs of about 27 steps
    ts, u, m = run_length_pulls("2025-01-01", start, end, step, rate, runs, seed=1)
    assert np.array_equal(ts, random_pulls("2025-01-01", start, end, step, rate, seed=1)[0])
    assert set(np.unique(u)) <= {-1.0, 0.0, 1.0} and not m.any()
    assert abs((u != 0).mean() - rate) < 0.02
    assert abs(toxic_episodes(u) / runs - 1) < 0.05
    assert abs((u == 1).sum() / (u != 0).sum() - 0.5) < 0.05
    # R at the same rate starts about rate * steps runs, many times more.
    r = random_pulls("2025-01-01", start, end, step, rate, seed=1)[1]
    assert toxic_episodes(r) > 10 * runs
    again = run_length_pulls("2025-01-01", start, end, step, rate, runs, seed=1)[1]
    other = run_length_pulls("2025-01-01", start, end, step, rate, runs, seed=2)[1]
    assert np.array_equal(u, again) and not np.array_equal(u, other)


def test_rl_with_no_pulls_and_with_runs_of_one_step():
    from toxic_flow.engine.run import run_length_pulls
    from toxic_flow.eval.metrics import toxic_episodes

    start, end, step = 10**12, 10**12 + 3600 * 10**9, 100_000_000
    assert not run_length_pulls("2025-01-01", start, end, step, 0.0, 0, seed=1)[1].any()
    # More runs than pulled steps can only come from the grid's extra points: L is 1.
    n = len(run_length_pulls("2025-01-01", start, end, step, 0.0, 0, seed=1)[0])
    u = run_length_pulls("2025-01-01", start, end, step, 0.01, int(0.01 * n) + 2, seed=1)[1]
    assert toxic_episodes(u) == (u != 0).sum()
    with pytest.raises(ValueError):
        run_length_pulls("2025-01-01", start, end, step, 0.6, 100, seed=1)


def test_rl_runs_as_b1_pulling_on_its_series():
    from toxic_flow.engine.run import _touch_args, run_length_pulls, utc_ns
    from toxic_flow.strategies.signal_input import EXTERNAL

    cfg = {"quote_start": "00:30:00", "quote_end": "23:59:00", "step_ns": 100_000_000}
    s = {"name": "RL", "design": "v2", "seed": 3, "k_ticks": 5,
         "pull_rate": {"2025-02-01": 0.2}, "episodes": {"2025-02-01": 7000}}  # fmt: skip
    args = _touch_args(s, "2025-02-01", cfg)
    want = run_length_pulls("2025-02-01", utc_ns("2025-02-01", "00:30:00"),
                            utc_ns("2025-02-01", "23:59:00"), 100_000_000, 0.2, 7000, 3)  # fmt: skip
    assert args[0] and args[1] == EXTERNAL and np.array_equal(args[4], want[0])
    assert np.array_equal(args[12], want[1])
    assert (args[14], args[15], args[16]) == (0.5, 5, np.inf)


def test_f_holds_a_side_in_the_loop_arguments():
    from toxic_flow.engine.run import _touch_args

    cfg = {"quote_start": "00:30:00", "quote_end": "23:59:00", "step_ns": 100_000_000}
    f = _touch_args({"name": "F", "design": "v2", "hold_s": 0.125}, "2025-01-01", cfg)
    b1 = _touch_args({"name": "B1", "design": "v2"}, "2025-01-01", cfg)
    assert f[0] is True and f[-1] == 125_000_000 and b1[-1] == 0
    assert all(np.array_equal(x, y) for x, y in zip(f[:-1], b1[:-1], strict=True))
