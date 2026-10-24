"""Run configs built from the training constants and configs/selected.yaml (engine/configs.py)."""

from collections import Counter

import pytest

from toxic_flow.engine import configs
from toxic_flow.engine.grid import expand

HAWKES = {"mu_b": 1.0, "mu_s": 1.1, "alpha_bb": 4.0, "alpha_bs": 0.4, "alpha_sb": 0.3,
          "alpha_ss": 4.1, "beta": 8.0}  # fmt: skip
K = {f"B2_ofi_{w}s": 10 + w for w in (1, 5, 30)} | {f"B2b_ewma_{t}s": 20 + t for t in (1, 5, 30)}
K |= {"B3_hawkes": 3.5, "C4_x10": 7.7, "C4_x0.1": 2.0}
CONSTANTS = {"label": "train", "hawkes": {"params": HAWKES}, "K": K}
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
    # B2b too, so the validation estimate of s (section 9) comes from this one run.
    # B3_c0 and C1_c0 are descriptive (audit A1): the selected B3 has c = 0.5 here.
    assert labels == {"B1": 1, "B2b": 1, "B3": 2, "C1": 1, "C2": 1, "C4_x10": 1, "C4_x0.1": 1,
                      "B3_c0": 1, "C1_c0": 1}  # fmt: skip
    c0 = {s["label"]: s for s in cfg["strategies"] if s.get("label", "").endswith("_c0")}
    assert all(s["c"] == 0.0 and s["d"] == 0.5 for s in c0.values())
    assert c0["C1_c0"]["seed"] == 1729 and c0["C1_c0"]["K"] == c0["B3_c0"]["K"]
    assert {c["latency"] for c in expand(cfg)} == {"high", "zero"}
    no_c = configs.canaries(CONSTANTS, {**SELECTED, "B3": {"c": 0.0, "d": 0.5}}, VAL)
    assert not any(s.get("label", "").endswith("_c0") for s in no_c["strategies"])


def test_smoke_constants_never_make_a_study_config():
    with pytest.raises(ValueError, match="smoke"):
        configs.tuning({**CONSTANTS, "label": "SMOKE: one day"}, SELECTED, VAL)


def test_training_selection_is_the_preregistered_grid_in_the_primary_cell():
    cfg = configs.training(["2024-01-01"])
    names = Counter(s["name"] for s in cfg["strategies"])
    assert names == {"B0": 4, "B1": 12}  # h in {1, 2, 3, 5}; 4 gammas x 3 windows
    assert len(expand(cfg)) == 16  # primary cell only
    assert {s["window_s"] for s in cfg["strategies"] if s["name"] == "B1"} == {300, 600, 1200}


def test_the_grid_edge_extension_adds_only_new_candidates():
    # Section 4 grid-edge rule: h 8 and 13; B1 on the 6 x 5 extended product less the 12
    # pairs the first run had, so 18 new pairs.
    cfg = configs.training_extended(["2024-01-01"])
    b0 = [s["h"] for s in cfg["strategies"] if s["name"] == "B0"]
    b1 = {(s["gamma"], s["window_s"]) for s in cfg["strategies"] if s["name"] == "B1"}
    first = {(s["gamma"], s["window_s"]) for s in configs.training(["2024-01-01"])["strategies"]
             if s["name"] == "B1"}  # fmt: skip
    assert b0 == [8, 13] and len(b1) == 18 and not b1 & first
    assert {g for g, _ in b1} | {g for g, _ in first} == {0.025, 0.05, 0.1, 0.2, 0.4, 0.8}
    assert {w for _, w in b1} | {w for _, w in first} == {300, 600, 1200, 2400, 4800}
    assert len(expand(cfg)) == 20  # primary cell only


def test_the_chosen_b0_and_b1_run_in_all_8_cells():
    cfg = configs.training_chosen(SELECTED, ["2024-01-01"])
    assert [s["name"] for s in cfg["strategies"]] == ["B0", "B1"]
    assert cfg["strategies"][0]["h"] == 2 and cfg["strategies"][1]["gamma"] == 0.1
    assert len(expand(cfg)) == 2 * 8
