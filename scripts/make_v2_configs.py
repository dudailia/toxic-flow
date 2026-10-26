#!/usr/bin/env python3
"""Run configs for the v2 design (PREREGISTRATION.md section 4 and Design history).

  uv run python scripts/make_v2_configs.py train      B0 and B1 on training days, 8 cells
  uv run python scripts/make_v2_configs.py tune       overlay grid on validation days
  uv run python scripts/make_v2_configs.py canaries   needs docs/M4_v2_selected.yaml
  uv run python scripts/make_v2_configs.py mde        needs docs/M4_v2_selected.yaml

tune writes two configs over disjoint halves of the validation days (v2_tune_val_a and
_b), so they can run side by side; the selection reads both. An existing config is never
overwritten: a committed config is what its results map to.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_configs import ROOT, kept  # noqa: E402

from toxic_flow.engine import configs  # noqa: E402

THRESHOLDS = ROOT / "docs" / "signals" / "train_thresholds.json"
SELECTED = ROOT / "docs" / "M4_v2_selected.yaml"


def write(cfg: dict) -> None:
    out = ROOT / "configs" / "runs" / f"{cfg['name']}.yaml"
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.write_text(
        "# Written by scripts/make_v2_configs.py (v2).\n" + yaml.safe_dump(cfg, sort_keys=False)
    )
    print(out, len(cfg["strategies"]), "strategies")


def main(kind: str) -> None:
    if kind == "train":
        write(configs.v2_training(kept("train")))
        return
    const = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    th = json.loads(THRESHOLDS.read_text())
    if kind == "tune":
        days = kept("val")
        half = len(days) // 2
        write(configs.v2_tuning(const, th, days[:half], name="v2_tune_val_a"))
        write(configs.v2_tuning(const, th, days[half:], name="v2_tune_val_b"))
        return
    selected = yaml.safe_load(SELECTED.read_text())
    if kind == "canaries":
        write(configs.v2_canaries(const, th, selected, kept("val")))
    elif kind == "mde":
        write(configs.v2_mde_train(const, th, selected, kept("train")))
    else:
        raise SystemExit(f"unknown kind {kind}")


if __name__ == "__main__":
    main(sys.argv[1])
