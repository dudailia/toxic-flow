#!/usr/bin/env python3
"""Rank one strategy's candidates in a run by the section 4 rule and print the table.

Usage: uv run python scripts/select_params.py results/<hash> <B0|B1|B2|B2b|B3> [out.md]

B0 and B1 are chosen on the training days, overlays on the validation days, less any
excluded day. A run that does not cover exactly those days gives a ranking labelled SMOKE,
which chooses nothing. The script never writes configs/selected.yaml: Ilia approves that
file from this table (SPEC.md AC2.5 and AC4.1).
"""

import json
import sys
from pathlib import Path

import polars as pl

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.eval.select import PRIMARY, candidate_table, select


def main(run_dir: Path, strategy: str, out: Path | None) -> None:
    if out is not None and out.name == "selected.yaml":
        raise SystemExit("configs/selected.yaml is written by hand after Ilia approves the table")
    meta = json.loads((run_dir / "meta.json").read_text())
    m = pl.read_parquet(run_dir / "metrics.parquet")
    split = "train" if strategy in ("B0", "B1") else "val"
    wanted = load_splits()[split]
    wanted = [d for d in wanted if d not in excluded_days(wanted)]
    run_days = sorted(set(m["day"]))
    full = run_days == sorted(wanted) and meta.get("label") != "smoke"
    days = wanted if full else run_days
    table = candidate_table(m, strategy, days)
    try:
        pick = select(table, strategy)
    except ValueError as e:  # no rule in section 4: leave the choice to Ilia
        pick = {"error": str(e)}
    kind = "Selection" if full else "SMOKE ranking (chooses nothing)"
    lines = [
        f"# {kind}: {strategy}, run {meta['config_hash']}",
        "",
        f"Primary cell {PRIMARY[0]} queue, {PRIMARY[1]} latency; {len(days)} {split if full else 'run'}"
        f" day(s): {', '.join(days)}. Rule: PREREGISTRATION.md section 4. From"
        f" {run_dir}/metrics.parquet by scripts/select_params.py.",
        "",
        "| Candidate | Mean daily BEF bp | Days | Days without fills |",
        "|---|---|---|---|",
    ]
    for r in table.sort("mean_bef_bps", descending=True, nulls_last=True).iter_rows(named=True):
        params = {k: v for k, v in json.loads(r["params"]).items() if k != "name"}
        lines.append(
            f"| {params} | {r['mean_bef_bps']:.4f} | {r['n_days']} | {r['zero_fill_days']} |"
        )
    head = "Selected, pending Ilia's approval" if full else "Top of the smoke ranking, not a choice"
    lines += ["", f"{head}: {pick}"]
    text = "\n".join(lines) + "\n"
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    print(text)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]) if len(sys.argv) > 3 else None)
