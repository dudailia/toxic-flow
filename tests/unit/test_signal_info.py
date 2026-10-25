"""The exploratory signal-information study (eval/signal_info.py)."""

import numpy as np

from toxic_flow.eval.signal_info import day_correlations, future_change, summarise


def test_future_change_looks_h_seconds_ahead_on_the_100_ms_grid():
    mid = np.arange(30, dtype=float)
    d = future_change(mid, 1)  # 10 steps
    assert np.all(d[:-10] == 10.0) and np.all(np.isnan(d[-10:]))


def test_a_signal_equal_to_the_future_direction_correlates_and_noise_does_not():
    rng = np.random.default_rng(1729)
    mid = np.cumsum(rng.choice([-1.0, 0.0, 1.0], 20_000))
    d = future_change(mid, 1)
    oracle = np.where(np.isfinite(d), np.sign(d), 0.0)
    noise = rng.uniform(-1, 1, len(mid))
    rows = day_correlations(mid, np.ones(len(mid), bool),
                            {"oracle": (oracle, np.abs(oracle)), "noise": (noise, np.abs(noise))})  # fmt: skip
    r = {(x["signal"], x["horizon_s"]): x for x in rows}
    assert r[("oracle", 1)]["corr_u"] > 0.8 and abs(r[("noise", 1)]["corr_u"]) < 0.05
    assert r[("oracle", 1)]["corr_m"] > 0.5


def test_summary_is_the_mean_daily_value_with_an_interval():
    s = summarise([0.1, 0.2, 0.3, float("nan")])
    assert s["days"] == 3 and abs(s["mean"] - 0.2) < 1e-12 and s["ci"][0] <= 0.2 <= s["ci"][1]
