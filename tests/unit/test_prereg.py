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
