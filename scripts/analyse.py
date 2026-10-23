#!/usr/bin/env python3
"""The pre-registered analysis from results/ only (eval/analysis.py).

uv run python scripts/analyse.py mde --train results/<h> --val results/<h>
    s and the MDE of section 9 (M4), printed as JSON.
uv run python scripts/analyse.py summary --s-bp <s> --out <file.json> results/<h> [...]
    H1, H2 to H4, markouts and canaries. --out results/summary.json, which make paper
    reads, is allowed only for non-smoke runs covering exactly the non-excluded test
    days, with s as frozen in PREREGISTRATION.md section 9.
"""

import argparse
import json
import subprocess
from pathlib import Path

import polars as pl

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
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


def tag_time() -> str:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "for-each-ref", "refs/tags/prereg-v1", "--format=%(creatordate:iso-strict)"],
        capture_output=True, text=True,
    )  # fmt: skip
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
        train, val = load([args.train])[0], load([args.val])[0]
        print(json.dumps(analysis.mde_inputs(train, val, n_test=len(kept("test"))), indent=2))
        return
    m, metas = load(args.dirs)
    out = Path(args.out).resolve()
    if out == PAPER_SUMMARY:
        problem = analysis.confirmatory_problem(metas, sorted(set(m["day"])), kept("test"))
        if problem:
            raise SystemExit(f"not writing {out}: {problem}")
    meta = {
        "hftbacktest": metas[0]["hftbacktest"],
        "prereg_pushed_at": tag_time(),
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
