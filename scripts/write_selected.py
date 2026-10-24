#!/usr/bin/env python3
"""Write configs/selected.yaml for B0 and B1 from the training selection run (M2, AC2.5).

Usage: uv run python scripts/write_selected.py results/<hash of configs/runs/train_select_window.yaml>

The rule is PREREGISTRATION.md section 4, applied by eval/select.py: on the non-excluded
training days, primary cell, the eligible candidate with the highest mean daily break-even
fee, every candidate scored from 01:20 to the end of quoting (the sel_* columns, Q45).
Eligible means a median training day of at least MIN_MEDIAN_FILLS fills in that window
(grid-edge rule, Q41). The file holds the chosen settings, the choice without the fill floor
(A2), and under "tables" every candidate's window and full-day mean BEF and median fills, so
the choice can be checked; docs/selection/<name>_train.md holds the same table and says
whether the choice is at an edge of the grid. If the rule does not decide (a tie, or a day
without fills), nothing is written and the script says why.
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
RUN = "configs/runs/train_select_window.yaml"
EDGE_PARAMS = {"B0": ("h",), "B1": ("gamma", "window_s")}


def grid_of(table: pl.DataFrame, name: str) -> dict[str, tuple]:
    """Each parameter's values among the candidates actually run, for the edge report."""
    params = [json.loads(p) for p in table["params"]]
    return {k: tuple(sorted({p[k] for p in params})) for k in EDGE_PARAMS[name]}


def plain(params: dict) -> dict:
    return {k: v for k, v in params.items() if k != "name"}


def fmt(x) -> str:
    return "none" if x is None else f"{x:.4f}"


def main(run_dir: Path) -> None:
    train = load_splits()["train"]
    days = sorted(d for d in train if d not in excluded_days(train))
    meta = json.loads((run_dir / "meta.json").read_text())
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text())
    if meta["config"] != RUN or meta.get("label") == "smoke" or "select_from" not in cfg:
        raise SystemExit(f"{run_dir} is not the training selection run with a scoring window")
    m = pl.read_parquet(run_dir / "metrics.parquet")
    if sorted(set(m["day"])) != days:
        raise SystemExit(f"{run_dir} covers {sorted(set(m['day']))}, not {days}")
    out = {"source": {"run": run_dir.name, "commit": meta["commit"], "config": RUN,
                      "days": days, "cell": list(PRIMARY), "scored_from": cfg["select_from"],
                      "rule": "PREREGISTRATION.md section 4, grid-edge rule and scoring window"}}  # fmt: skip
    tables, edges, no_floor, docs = {}, {}, {}, {}
    for name in ("B0", "B1"):
        win = candidate_table(m, name, days, prefix="sel_")
        pick = select(win, name)  # raises where section 4 has no rule
        out[name] = plain(pick["params"])
        # A2: the same rule without the fill floor, to show whether the floor decided.
        unfloored = win.filter(pl.col("zero_fill_days") == 0)
        best = unfloored.sort("mean_bef_bps", descending=True, nulls_last=True)
        no_floor[name] = plain(json.loads(best["params"][0])) if best.height else None
        grid = grid_of(win, name)
        edges[name] = {k: e for k, g in grid.items() if (e := at_edge(out[name][k], g))}
        full = candidate_table(m, name, days).select(
            "params", full_bef=pl.col("mean_bef_bps"), full_fills=pl.col("median_fills")
        )
        # NaN (a day without fills) would sort above every number in polars; list it last.
        table = (
            win.with_columns(
                eligible=eligible(win), mean_bef_bps=pl.col("mean_bef_bps").fill_nan(None)
            )
            .join(full.with_columns(pl.col("full_bef").fill_nan(None)), on="params")
            .sort("mean_bef_bps", descending=True, nulls_last=True)
        )
        tables[name] = [
            {**plain(json.loads(r["params"])),
             "window_mean_daily_bef_bps": None if r["mean_bef_bps"] is None else round(r["mean_bef_bps"], 6),
             "window_median_daily_fills": float(r["median_fills"]), "eligible": r["eligible"],
             "full_day_mean_daily_bef_bps": None if r["full_bef"] is None else round(r["full_bef"], 6),
             "full_day_median_daily_fills": float(r["full_fills"])}
            for r in table.iter_rows(named=True)
        ]  # fmt: skip
        lines = [
            f"# {name} selection on the training days (M2)",
            "",
            f"Run {run_dir.name} ({RUN}, commit {meta['commit'][:7]}); primary cell {PRIMARY[0]} /",
            f"{PRIMARY[1]}; {len(days)} days. Rule (PREREGISTRATION.md section 4): highest mean daily",
            f"break-even fee scored from {cfg['select_from']} to the end of quoting, among candidates",
            f"with a median training day of at least {MIN_MEDIAN_FILLS} fills in that window. The",
            "grid-edge rule and the scoring window were added on 2026-10-24, after the first",
            "selection had been seen. Full-day columns are for reference.",
            "",
            "| Candidate | Window mean BEF bp | Window median fills | Eligible | Full-day mean BEF bp | Full-day median fills |",
            "|---|---|---|---|---|---|",
            *(f"| {json.dumps({k: v for k, v in t.items() if k in EDGE_PARAMS[name] + ('update_every',)})} "
              f"| {fmt(t['window_mean_daily_bef_bps'])} | {t['window_median_daily_fills']:.0f} "
              f"| {'yes' if t['eligible'] else 'no'} | {fmt(t['full_day_mean_daily_bef_bps'])} "
              f"| {t['full_day_median_daily_fills']:.0f} |" for t in tables[name]),
            "",
            f"Chosen: {json.dumps(out[name])}",
            f"Without the fill floor (and leaving out candidates with a day without fills) the rule would choose: {json.dumps(no_floor[name])}"
            + (" (the same)" if no_floor[name] == out[name] else " (the floor decided the choice)"),
            "At the edge of its grid: "
            + (", ".join(f"{k} ({e} end of {list(grid[k])})" for k, e in edges[name].items())
               or "no"),
        ]  # fmt: skip
        docs[name] = "\n".join(lines) + "\n"
    # Write only once both choices are made, so a failed B1 rule leaves no new B0 file.
    for name, text in docs.items():
        path = ROOT / "docs" / "selection" / f"{name}_train.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    out["without_fill_floor"] = no_floor
    out["at_edge"] = edges
    out["tables"] = tables
    target = ROOT / "configs" / "selected.yaml"
    target.write_text(
        "# B0 and B1 chosen on the training days by scripts/write_selected.py (M2, AC2.5).\n"
        "# B2, B2b and B3 are added in M4 from the validation tuning.\n"
        + yaml.safe_dump(out, sort_keys=False)
    )
    print(target, json.dumps({k: out[k] for k in ("B0", "B1", "without_fill_floor", "at_edge")}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
