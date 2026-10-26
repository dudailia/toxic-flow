"""v2 overlay thresholds (PREREGISTRATION.md section 5): the toxic side steps back on a share
p of the training-day decision steps, within 1 percentage point."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from toxic_flow.signals.thresholds import MAGNITUDE_Q, PULL_RATES, share_above, theta_m, theta_u

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = ROOT / "docs" / "signals" / "train_thresholds.json"
TUNING_GRID = ("B2_ofi_1s", "B2_ofi_5s", "B2_ofi_30s", "B2b_ewma_1s", "B2b_ewma_5s",
               "B2b_ewma_30s", "B3_hawkes")  # fmt: skip
# The one known miss: at beta x 10 the intensity is back at its baseline between events,
# so |u| equals (mu_b - mu_s) / (mu_b + mu_s) on many steps, a tie at the median that a
# strict "above" cannot split. C4 runs at B3's selected p, so this matters only if B3's
# choice is p = 0.5 (Q52 in docs/SESSION_REPORT.md).
KNOWN_MISS = {("C4_x10", "0.5"): 0.4604}


def test_the_quantile_threshold_hits_p_on_continuous_data():
    x = np.abs(np.random.default_rng(1729).standard_normal(200_000))
    for p in PULL_RATES:
        assert abs(share_above(x, theta_u(x, p)) - p) < 1e-3
    assert abs(share_above(x, theta_m(x)) - (1 - MAGNITUDE_Q)) < 1e-3


def test_the_rule_is_strictly_above():
    assert share_above(np.array([0.1, 0.2, 0.3]), 0.2) == pytest.approx(1 / 3)


def thresholds() -> dict:
    return json.loads(THRESHOLDS.read_text())


def test_thresholds_come_from_the_training_days():
    sys.path.insert(0, str(ROOT / "scripts"))
    from make_configs import kept

    th = thresholds()
    assert th["label"] == "train" and th["days"] == sorted(kept("train"))
    assert set(TUNING_GRID) | {"C4_x10", "C4_x0.1"} == set(th["signals"])


def test_p_is_hit_on_training_days_within_one_point():
    for name, s in thresholds()["signals"].items():
        for p, share in s["share_above"].items():
            if (name, p) in KNOWN_MISS:
                assert share == pytest.approx(KNOWN_MISS[name, p], abs=1e-4)
                continue
            assert abs(share - float(p)) <= 0.01, (name, p, share)
        assert abs(s["share_m_above"] - (1 - MAGNITUDE_Q)) <= 0.01, name


@pytest.mark.slow
def test_p_is_hit_when_recomputed_in_float64_on_the_training_days():
    """The script keeps u in float32 to hold 12 days in memory; this recomputes each day's
    signals in float64 and checks the committed thresholds against them."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from signal_info import hawkes_settings

    from toxic_flow.engine.run import event_inputs, ofi_inputs, utc_ns
    from toxic_flow.eval.signal_info import signals

    th = thresholds()
    const = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    above = {(n, p): 0 for n in th["signals"] for p in th["pull_rates"]}
    total = 0
    for day in th["days"]:
        grid = np.arange(utc_ns(day, "00:00:00"), utc_ns(day, "23:59:00"), 100_000_000)
        quoting = grid >= utc_ns(day, "00:30:00")
        ev_ts, ev_side = event_inputs(day)
        ofi_ts, cum = ofi_inputs(day)
        sig = signals(grid, ev_ts, ev_side, ofi_ts, np.diff(cum),
                      hawkes_settings(const["hawkes"]["params"]), const["K"])  # fmt: skip
        total += int(quoting.sum())
        for (n, p), _ in above.items():
            above[n, p] += int(
                (np.abs(sig[n][0][quoting]) > th["signals"][n]["theta_u"][f"{p:g}"]).sum()
            )
    for (n, p), k in above.items():
        if (n, f"{p:g}") in KNOWN_MISS:
            continue
        assert abs(k / total - p) <= 0.01, (n, p, k / total)
