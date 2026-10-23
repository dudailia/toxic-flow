#!/usr/bin/env python3
"""Write a study run config into configs/runs/ (builders in engine/configs.py).

  uv run python scripts/make_configs.py training --gammas 0.05,0.1 --windows 300,600
  uv run python scripts/make_configs.py tuning | canaries | mde_train | confirmatory

training needs only Ilia's B1 grid (Q23). The others read docs/signals/train_constants.json
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
SPLIT = {"training": "train", "tuning": "val", "canaries": "val", "mde_train": "train",
         "confirmatory": "test"}  # fmt: skip


def kept(split: str) -> list[str]:
    days = load_splits()[split]
    return [d for d in days if d not in excluded_days(days)]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=list(SPLIT))
    p.add_argument("--gammas")
    p.add_argument("--windows")
    args = p.parse_args()
    days = kept(SPLIT[args.kind])
    if args.kind == "training":
        if not (args.gammas and args.windows):
            raise SystemExit(
                "the B1 gamma and window grid is Ilia's choice (Q23): pass --gammas and --windows"
            )
        cfg = configs.training(
            [float(g) for g in args.gammas.split(",")],
            [int(w) for w in args.windows.split(",")],
            days,
        )
    else:
        constants = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
        selected = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
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
