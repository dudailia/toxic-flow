"""Run configs built from the training constants and configs/selected.yaml (engine/configs.py)."""

from collections import Counter

import pytest

from toxic_flow.engine import configs
from toxic_flow.engine.grid import expand

HAWKES = {"mu_b": 1.0, "mu_s": 1.1, "alpha_bb": 4.0, "alpha_bs": 0.4, "alpha_sb": 0.3,
          "alpha_ss": 4.1, "beta": 8.0}  # fmt: skip
K = {f"B2_ofi_{w}s": 10 + w for w in (1, 5, 30)} | {f"B2b_ewma_{t}s": 20 + t for t in (1, 5, 30)}
CONSTANTS = {"label": "train", "hawkes": {"params": HAWKES}, "K": K | {"B3_hawkes": 3.5}}
SELECTED = {
    "B0": {"h": 2},
    "B1": {"gamma": 0.1, "window_s": 300, "update_every": 50},
    "B2": {"c": 0.5, "d": 1.0, "ofi_window_s": 30.0},
    "B2b": {"c": 1.0, "d": 0.0, "tau_s": 1.0},
    "B3": {"c": 0.5, "d": 0.5},
}
VAL = [f"2025-0{m}-01" for m in range(1, 7)]


def test_tuning_grid_is_27_27_9_candidates_on_b1_with_their_own_k():
    cfg = configs.tuning(CONSTANTS, SELECTED, VAL)
    names = Counter(s["name"] for s in cfg["strategies"])
    assert names == {"B2": 27, "B2b": 27, "B3": 9}
    assert len(expand(cfg)) == 63 * 6  # primary cell only
    b2 = next(s for s in cfg["strategies"] if s["name"] == "B2" and s["ofi_window_s"] == 30.0)
    assert b2["K"] == K["B2_ofi_30s"] and b2["gamma"] == 0.1 and b2["window_s"] == 300
    b3 = next(s for s in cfg["strategies"] if s["name"] == "B3")
    assert b3["beta"] == HAWKES["beta"] and b3["K"] == 3.5


def test_confirmatory_grid_is_one_config_with_canaries_in_the_primary_cell():
    days = ["2025-07-01", "2025-08-01"]
    cfg = configs.confirmatory(CONSTANTS, SELECTED, days)
    cells = [(c["strategy"].get("label", c["strategy"]["name"]), c["queue"], c["latency"])
             for c in expand(cfg)]  # fmt: skip
    # 5 strategies in 8 cells, 4 canaries in the primary cell, and C3 (B3 at zero latency).
    assert len(cells) == (5 * 8 + 4 + 1) * 2
    assert ("C1", "risk_averse", "high") in cells and ("B3", "risk_averse", "zero") in cells
    assert not any(lat == "zero" for name, _, lat in cells if name != "B3")
    c1 = next(s for s in cfg["strategies"] if s["name"] == "C1")
    assert (c1["c"], c1["d"], c1["seed"]) == (0.5, 0.5, 1729)


def test_canary_config_for_validation_days():
    cfg = configs.canaries(CONSTANTS, SELECTED, VAL)
    labels = Counter(s.get("label", s["name"]) for s in cfg["strategies"])
    assert labels == {"B1": 1, "B3": 2, "C1": 1, "C2": 1, "C4_x10": 1, "C4_x0.1": 1}
    assert {c["latency"] for c in expand(cfg)} == {"high", "zero"}


def test_smoke_constants_never_make_a_study_config():
    with pytest.raises(ValueError, match="smoke"):
        configs.tuning({**CONSTANTS, "label": "SMOKE: one day"}, SELECTED, VAL)


def test_training_grid_needs_the_b1_grid_from_ilia():
    cfg = configs.training([0.05, 0.1], [300, 600], ["2024-01-01"])
    names = Counter(s["name"] for s in cfg["strategies"])
    assert names == {"B0": 4, "B1": 4}
    assert len(expand(cfg)) == 8 * 8
