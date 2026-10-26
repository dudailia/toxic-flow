#!/usr/bin/env python3
"""The pre-registered analysis from results/ only (eval/analysis.py).

uv run python scripts/analyse.py mde --train results/<h> --val results/<h>
    s and the MDE of section 9 (M4), printed as JSON.
uv run python scripts/analyse.py summary --s-bp <s> --out <file.json> results/<h> [...]
    H1, H2 to H4, markouts and canaries. --out results/summary.json, which make paper
    reads, is allowed only for the two planned test-day runs, configs/runs/confirmatory.yaml
    and its random-pull controls configs/runs/confirmatory_controls.yaml (same config
    hashes, made at commits after prereg-v1), with every label on every non-excluded test
    day in each of its cells, each control at its strategy's realised rate, and with
    --s-bp equal to s as frozen in PREREGISTRATION.md section 9.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

import polars as pl
import yaml

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.engine.configs import frozen_hold
from toxic_flow.engine.grid import config_hash
from toxic_flow.eval import analysis

ROOT = Path(__file__).resolve().parents[1]
PAPER_SUMMARY = ROOT / "results" / "summary.json"


def kept(split: str) -> list[str]:
    days = load_splits()[split]
    return [d for d in days if d not in excluded_days(days)]


def load(dirs) -> tuple[pl.DataFrame, list[dict]]:
    metas = [json.loads((Path(d) / "meta.json").read_text()) for d in dirs]
    frames = [pl.read_parquet(Path(d) / "metrics.parquet") for d in dirs]
    frames = [
        f if "label" in f.columns else f.with_columns(label=pl.col("strategy")) for f in frames
    ]
    return pl.concat(frames, how="diagonal_relaxed"), metas


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def frozen_s() -> float | None:
    """s from PREREGISTRATION.md section 9 ("s = <number> bp"), or None while it is [TBD]."""
    found = re.search(r"^s = ([0-9.]+) bp", (ROOT / "PREREGISTRATION.md").read_text(), re.M)
    return float(found.group(1)) if found else None


def paper_problem(metas: list[dict], s_bp: float) -> str | None:
    """The checks that need git and files; analysis.confirmatory_problem does the rest."""
    s = frozen_s()
    if s is None or abs(s - s_bp) > 1e-12:
        return f"--s-bp {s_bp} is not the s frozen in section 9 ({s})"
    for meta in metas:
        cfg = yaml.safe_load((ROOT / meta["config"]).read_text())
        if meta["config_hash"] != config_hash(cfg):
            return f"run {meta['config_hash']} is not {meta['config']} as committed"
        if git("merge-base", "--is-ancestor", "prereg-v1", meta["commit"]).returncode != 0:
            return f"run {meta['config_hash']} was made at a commit before prereg-v1"
    return None


def tag_time() -> str:
    # Creation time of the annotated tag; the push time is Ilia's entry in DEVIATIONS.md.
    out = git("for-each-ref", "refs/tags/prereg-v1", "--format=%(creatordate:iso-strict)")
    return out.stdout.strip() or "[no prereg-v1 tag]"


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("mde")
    a.add_argument("--train", required=True)
    a.add_argument("--val", required=True)
    b = sub.add_parser("summary")
    b.add_argument("--s-bp", type=float, required=True)
    b.add_argument("--out", required=True)
    b.add_argument("dirs", nargs="+")
    args = p.parse_args()

    if args.cmd == "mde":
        runs = {"train": load([args.train]), "val": load([args.val])}
        for split, (m, metas) in runs.items():
            if metas[0].get("label") == "smoke" or sorted(set(m["day"])) != sorted(kept(split)):
                raise SystemExit(f"--{split} must be a non-smoke run on every kept {split} day")
        n_test = len(kept("test"))
        print(json.dumps(analysis.mde_inputs(runs["train"][0], runs["val"][0], n_test), indent=2))
        return
    m, metas = load(args.dirs)
    out = Path(args.out).resolve()
    if out == PAPER_SUMMARY:
        selected = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
        hold = frozen_hold(selected)  # F's hold, checked against the training-day rule
        problem = analysis.confirmatory_problem(metas, m, kept("test"), hold) or paper_problem(
            metas, args.s_bp
        )
        if problem:
            raise SystemExit(f"not writing {out}: {problem}")
    meta = {
        "hftbacktest": metas[0]["hftbacktest"],
        "prereg_tagged_at": tag_time(),
        "n_train_days": len(kept("train")),
        "n_val_days": len(kept("val")),
        "runs": [
            {"config_hash": x["config_hash"], "commit": x["commit"], "label": x.get("label", "")}
            for x in metas
        ],
    }
    summary = analysis.summary(m, {"s_bp": args.s_bp}, meta) | {"runs": meta["runs"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
