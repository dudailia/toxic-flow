#!/usr/bin/env python3
"""Write a study run config into configs/runs/ (builders in engine/configs.py).

  uv run python scripts/make_configs.py training
  uv run python scripts/make_configs.py training_chosen | tuning | canaries | mde_train | confirmatory

training is the section 4 selection grid. training_chosen reads configs/selected.yaml; the
others also read docs/signals/train_constants.json
(from scripts/fit_signals.py) and configs/selected.yaml (written by hand after Ilia approves
a selection table). Days are the split's days less any excluded day. The script never
writes configs/selected.yaml and never overwrites an existing config: a changed config is a
new file, so every results directory keeps the config that produced it.
"""

import argparse
import json
from pathlib import Path

import yaml

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.engine import configs

ROOT = Path(__file__).resolve().parents[1]
SPLIT = {"training": "train", "training_chosen": "train", "tuning": "val", "canaries": "val",
         "mde_train": "train", "confirmatory": "test"}  # fmt: skip


def kept(split: str) -> list[str]:
    """The split's days less any excluded day, smallest raw size first, so the largest days
    convert last (Ilia, 2026-10-23). The order of days does not change any result."""
    days = load_splits()[split]
    raw = {}
    for e in json.loads((ROOT / "data" / "manifest.json").read_text())["files"]:
        raw[e["date"]] = raw.get(e["date"], 0) + e["bytes"]
    return sorted((d for d in days if d not in excluded_days(days)), key=lambda d: raw.get(d, 0))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=list(SPLIT))
    args = p.parse_args()
    days = kept(SPLIT[args.kind])
    if args.kind == "training":
        cfg = configs.training(days)
    else:
        selected = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
        if args.kind == "training_chosen":
            cfg = configs.training_chosen(selected, days)
        else:
            constants = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
            cfg = getattr(configs, args.kind)(constants, selected, days)
    out = ROOT / "configs" / "runs" / f"{cfg['name']}.yaml"
    if out.exists():
        raise SystemExit(f"{out} exists; a changed config needs a new name")
    out.write_text(
        f"# Written by scripts/make_configs.py {args.kind}.\n"
        + yaml.safe_dump(cfg, sort_keys=False)
    )
    print(out)


if __name__ == "__main__":
    main()
