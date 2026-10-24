#!/usr/bin/env python3
"""Write configs/selected.yaml for B0 and B1 from the training selection runs (M2, AC2.5).

Usage: uv run python scripts/write_selected.py results/<train_select hash> [results/<train_select_ext hash>]

The rule is PREREGISTRATION.md section 4, applied by eval/select.py: on the non-excluded
training days, primary cell, the eligible candidate with the highest mean daily break-even
fee. Eligible means a median training day of at least 100 fills (grid-edge rule, Q41). With
the grid-edge extension run given too, the selection is over both runs' candidates together.
The file holds the chosen settings and, under "tables", every candidate's mean daily BEF,
median daily fills and eligibility, so the choice can be checked; docs/selection/
<name>_train.md holds the same table and says whether the choice is at an edge of the grid.
If the rule does not decide (a tie, or a day without fills), nothing is written and the
script says why.
"""

import json
import sys
from pathlib import Path

import polars as pl
import yaml

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.eval.select import (
    MIN_MEDIAN_FILLS,
    PRIMARY,
    at_edge,
    candidate_table,
    eligible,
    select,
)

ROOT = Path(__file__).resolve().parents[1]
RUNS = ("configs/runs/train_select.yaml", "configs/runs/train_select_ext.yaml")


EDGE_PARAMS = {"B0": ("h",), "B1": ("gamma", "window_s")}
# Run settings that must agree for two runs' candidates to be ranked together.
SAME = ("queue_models", "latencies", "quote_start", "quote_end", "step_ns", "max_lots",
        "fee_levels_bps")  # fmt: skip


def grid_of(table: pl.DataFrame, name: str) -> dict[str, tuple]:
    """Each parameter's values among the candidates actually run, for the edge report."""
    params = [json.loads(p) for p in table["params"]]
    return {k: tuple(sorted({p[k] for p in params})) for k in EDGE_PARAMS[name]}


def main(run_dirs: list[Path]) -> None:
    train = load_splits()["train"]
    days = sorted(d for d in train if d not in excluded_days(train))
    metas, frames, cfgs = [], [], []
    for run_dir in run_dirs:
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta["config"] not in RUNS or meta.get("label") == "smoke":
            raise SystemExit(f"{run_dir} is not a training selection run")
        cfg = yaml.safe_load((run_dir / "config.yaml").read_text())
        cfgs.append(({k: cfg[k] for k in SAME}, meta["hftbacktest"]))
        m = pl.read_parquet(run_dir / "metrics.parquet")
        if sorted(set(m["day"])) != days:
            raise SystemExit(f"{run_dir} covers {sorted(set(m['day']))}, not {days}")
        metas.append({"run": run_dir.name, "commit": meta["commit"], "config": meta["config"]})
        frames.append(m)
    if [x["config"] for x in metas][:1] != [RUNS[0]] or len({x["config"] for x in metas}) < len(
        metas
    ):
        raise SystemExit("give the train_select run first, then at most one extension run")
    if any(c != cfgs[0] for c in cfgs):
        raise SystemExit(f"the runs differ in settings or hftbacktest version: {cfgs}")
    m = pl.concat(frames, how="diagonal_relaxed")
    grid, docs = {}, {}
    out = {"source": {"runs": metas, "days": days, "cell": list(PRIMARY),
                      "rule": "PREREGISTRATION.md section 4, with the grid-edge rule"}}  # fmt: skip
    tables, edges = {}, {}
    for name in ("B0", "B1"):
        table = candidate_table(m, name, days)
        pick = select(table, name)  # raises where section 4 has no rule
        out[name] = {k: v for k, v in pick["params"].items() if k != "name"}
        grid[name] = grid_of(table, name)
        edges[name] = {k: e for k, g in grid[name].items() if (e := at_edge(out[name][k], g))}
        # NaN (a day without fills) would sort above every number in polars; list it last.
        table = table.with_columns(
            eligible=eligible(table), mean_bef_bps=pl.col("mean_bef_bps").fill_nan(None)
        )
        rows = table.sort("mean_bef_bps", descending=True, nulls_last=True).iter_rows(named=True)
        tables[name] = [
            {**{k: v for k, v in json.loads(r["params"]).items() if k != "name"},
             "mean_daily_bef_bps": None if r["mean_bef_bps"] is None else round(r["mean_bef_bps"], 6),
             "median_daily_fills": float(r["median_fills"]), "eligible": r["eligible"]}
            for r in rows
        ]  # fmt: skip
        stats = ("mean_daily_bef_bps", "median_daily_fills", "eligible")
        lines = [
            f"# {name} selection on the training days (M2)",
            "",
            "Runs " + ", ".join(f"{x['run']} ({x['config']}, commit {x['commit'][:7]})" for x in metas)
            + f"; primary cell {PRIMARY[0]} / {PRIMARY[1]}; {len(days)} days.",
            "Rule: highest mean daily break-even fee among candidates with a median training day of",
            f"at least {MIN_MEDIAN_FILLS} fills (PREREGISTRATION.md section 4, grid-edge rule added",
            "2026-10-24 after the first selection was seen).",
            "",
            "| Candidate | Mean daily BEF bp | Median daily fills | Eligible |",
            "|---|---|---|---|",
            *(f"| {json.dumps({k: v for k, v in t.items() if k not in stats})} | "
              f"{'none' if t['mean_daily_bef_bps'] is None else format(t['mean_daily_bef_bps'], '.4f')} | "
              f"{t['median_daily_fills']:.0f} | "
              f"{'yes' if t['eligible'] else 'no'} |" for t in tables[name]),
            "",
            f"Chosen: {json.dumps(out[name])}",
            "At the edge of its grid: "
            + (", ".join(f"{k} ({e} end of {list(grid[name][k])})" for k, e in edges[name].items())
               or "no"),
        ]  # fmt: skip
        docs[name] = "\n".join(lines) + "\n"
    # Write only once both choices are made, so a failed B1 rule leaves no new B0 file.
    for name, text in docs.items():
        path = ROOT / "docs" / "selection" / f"{name}_train.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    out["at_edge"] = edges
    out["tables"] = tables
    target = ROOT / "configs" / "selected.yaml"
    target.write_text(
        "# B0 and B1 chosen on the training days by scripts/write_selected.py (M2, AC2.5).\n"
        "# B2, B2b and B3 are added in M4 from the validation tuning.\n"
        + yaml.safe_dump(out, sort_keys=False)
    )
    print(target, json.dumps({k: out[k] for k in ("B0", "B1", "at_edge")}))


if __name__ == "__main__":
    main([Path(a) for a in sys.argv[1:]])
