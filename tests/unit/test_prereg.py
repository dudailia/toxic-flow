"""AC4.4: PREREGISTRATION.md has no [TBD] left (tests/test_writing.py lints its wording),
and the numbers filled into it match the committed files they come from."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "PREREGISTRATION.md").read_text()


def test_no_tbd_is_left():
    assert "[TBD" not in TEXT


def test_thresholds_table_matches_the_training_file():
    th = json.loads((ROOT / "docs" / "signals" / "train_thresholds.json").read_text())
    for name, s in th["signals"].items():
        row = f"| {name} | " + " | ".join(
            f"{s['theta_u'][p]:.4f}" for p in ("0.05", "0.1", "0.25", "0.5")
        )
        assert row + f" | {s['theta_m']:.4f} |" in TEXT


def test_selected_settings_match_configs_selected():
    sel = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
    assert sel["B2"] == {"k_ticks": "pull", "magnitude": False, "ofi_window_s": 5.0, "p": 0.25}
    assert sel["B2b"] == {"k_ticks": "pull", "magnitude": False, "p": 0.25, "tau_s": 5.0}
    assert sel["B3"] == {"k_ticks": "pull", "magnitude": False, "p": 0.05}
    assert "B2 with W = 5 s at p = 25%; B2b with tau = 5 s at p = 25%; B3 at\np = 5%" in TEXT


def test_the_summary_guard_reads_the_frozen_s_and_it_is_the_measured_one():
    # scripts/analyse.py refuses results/summary.json unless --s-bp equals the s read here.
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from analyse import frozen_s

    pre = json.loads((ROOT / "paper" / "pre_test.json").read_text())
    assert frozen_s() == float(pre["pre_s"])
    assert f"MDE = 0.70 s = {pre['pre_mde']} bp." in TEXT


def test_f_hold_is_the_training_day_rule_on_the_committed_run():
    import polars as pl

    from toxic_flow.engine.configs import F_HOLDS_S, choose_hold, frozen_hold

    sel = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
    grid = pl.read_parquet(ROOT / "results" / "83bb2b991997" / "metrics.parquet")
    b3 = pl.read_parquet(ROOT / "results" / "58c46cc49981" / "metrics.parquet")
    target = b3.filter(pl.col("label") == "B3")["toxic_share"].mean()
    shares = {
        h: grid.filter(pl.col("label") == f"F_h{h:g}")["toxic_share"].mean() for h in F_HOLDS_S
    }
    assert frozen_hold(sel) == choose_hold(shares, target) == 0.1
    assert f"h = {frozen_hold(sel):g} s" in TEXT
