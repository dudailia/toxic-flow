#!/usr/bin/env python3
"""Run configs for the v2 design (PREREGISTRATION.md section 4 and Design history).

  uv run python scripts/make_v2_configs.py train      B0 and B1 on training days, 8 cells
  uv run python scripts/make_v2_configs.py tune       overlay grid on validation days
  uv run python scripts/make_v2_configs.py canaries   needs docs/M4_v2_selected.yaml
  uv run python scripts/make_v2_configs.py mde        needs docs/M4_v2_selected.yaml
  uv run python scripts/make_v2_configs.py random results/<v2_canaries_val>
      random-pull controls; the rates are the realised toxic shares of C1, B3 and B2b in
      that run, primary cell, per day
  uv run python scripts/make_v2_configs.py runlength results/<v2_canaries_val>
      run-length controls RL_B3 and RL_B2b (exploratory): B3's and B2b's realised toxic
      shares and numbers of toxic episodes in that run, primary cell, per day
  uv run python scripts/make_v2_configs.py confirmatory   needs configs/selected.yaml
  uv run python scripts/make_v2_configs.py controls results/<confirmatory>
      M5, the two planned test-day runs (section 10): the grid on the kept test days, then
      the random-pull controls at that run's realised toxic shares (and, for RL, numbers
      of toxic episodes). Only after prereg-v1
      and the exclusion step (SPEC.md AC5.2), since the kept test days need both.

tune writes two configs over disjoint halves of the validation days (v2_tune_val_a and
_b), so they can run side by side; the selection reads both. An existing config is never
overwritten: a committed config is what its results map to.
"""

import json
import sys
from pathlib import Path

import polars as pl
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


def realised_rates(run: Path, config: str, column: str = "toxic_share") -> dict:
    """{C1, B3, B2b: {day: value of column}} in the primary cell of a committed run of
    configs/runs/<config>.yaml: the toxic share, or the number of toxic episodes."""
    meta = json.loads((run / "meta.json").read_text())
    if meta["config"] != f"configs/runs/{config}.yaml":
        raise SystemExit(f"{run} is not {config}")
    m = pl.read_parquet(run / "metrics.parquet").filter(
        (pl.col("queue") == configs.PRIMARY[0]) & (pl.col("latency") == configs.PRIMARY[1])
    )
    return {lab: {d: x for d, x in m.filter(pl.col("label") == lab)
                  .select("day", column).iter_rows()}
            for lab in ("C1", "B3", "B2b")}  # fmt: skip


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
    elif kind == "random":
        rates = realised_rates(Path(sys.argv[2]), "v2_canaries_val")
        write(configs.v2_random_pulls(const, th, selected, rates, kept("val")))
    elif kind == "runlength":
        run = Path(sys.argv[2])
        rates = realised_rates(run, "v2_canaries_val")
        runs = realised_rates(run, "v2_canaries_val", "toxic_episodes")
        episodes = {k: runs[k] for k in ("B3", "B2b")}
        write(configs.v2_run_length(const, th, selected, rates, episodes, kept("val")))
    elif kind in ("confirmatory", "controls"):
        approved = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
        if kind == "confirmatory":
            write(configs.v2_confirmatory(const, th, approved, kept("test")))
        else:
            run = Path(sys.argv[2])
            rates = realised_rates(run, "confirmatory")
            runs = realised_rates(run, "confirmatory", "toxic_episodes")
            episodes = {k: runs[k] for k in ("B3", "B2b")}
            write(configs.v2_confirmatory_controls(approved, rates, episodes, kept("test")))
    else:
        raise SystemExit(f"unknown kind {kind}")


if __name__ == "__main__":
    main(sys.argv[1])
