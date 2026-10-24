#!/usr/bin/env python3
"""Write a study run config into configs/runs/ (builders in engine/configs.py).

  uv run python scripts/make_configs.py training
  uv run python scripts/make_configs.py training_chosen | tuning | canaries | mde_train | confirmatory

training is the section 4 selection grid, training_extended its grid-edge extension (Q41),
training_window both grids scored from 01:20 (Q45).
training_chosen reads configs/selected.yaml; the
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
SPLIT = {"training": "train", "training_extended": "train", "training_window": "train", "training_chosen": "train", "tuning": "val", "canaries": "val",
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
    # M4 drafts read the overlay choice from a draft file, so configs/selected.yaml keeps
    # only what Ilia has approved (Ilia, 2026-10-24: M4 is reviewed before it is filled in).
    p.add_argument("--selected", type=Path, default=ROOT / "configs" / "selected.yaml")
    # A changed config is a new file (see above), so a rerun after a new selection gets a
    # suffix, such as train_chosen_window.
    p.add_argument("--suffix", default="")
    args = p.parse_args()
    days = kept(SPLIT[args.kind])
    if args.kind == "training":
        cfg = configs.training(days)
    elif args.kind == "training_extended":
        cfg = configs.training_extended(days)
    elif args.kind == "training_window":
        cfg = configs.training_window(days)
    else:
        selected = yaml.safe_load(args.selected.read_text())
        if args.kind == "training_chosen":
            cfg = configs.training_chosen(selected, days)
        else:
            constants = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
            cfg = getattr(configs, args.kind)(constants, selected, days)
    if args.selected.resolve() != (ROOT / "configs" / "selected.yaml").resolve():
        cfg["name"] = cfg["label"] = f"{cfg['name']}_draft"  # never the approved config's name
    if args.suffix:
        cfg["name"] = cfg["label"] = f"{cfg['name']}_{args.suffix}"
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
