#!/usr/bin/env python3
"""Write configs/selected.yaml for B0 and B1 from the training selection run (M2, AC2.5).

Usage: uv run python scripts/write_selected.py results/<hash of configs/runs/train_select.yaml>

The rule is PREREGISTRATION.md section 4, applied by eval/select.py: on the non-excluded
training days, primary cell, the candidate with the highest mean daily break-even fee. The
file holds the chosen settings and, under "tables", every candidate's mean daily BEF, so
the choice can be checked; docs/selection/<name>_train.md holds the same table. If the rule
does not decide (a tie, or a day without fills), nothing is written and the script says why.
"""

import json
import sys
from pathlib import Path

import polars as pl
import yaml

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.eval.select import PRIMARY, candidate_table, select

ROOT = Path(__file__).resolve().parents[1]


def main(run_dir: Path) -> None:
    meta = json.loads((run_dir / "meta.json").read_text())
    if meta["config"] != "configs/runs/train_select.yaml" or meta.get("label") == "smoke":
        raise SystemExit(f"{run_dir} is not the training selection run")
    train = load_splits()["train"]
    days = sorted(d for d in train if d not in excluded_days(train))
    m = pl.read_parquet(run_dir / "metrics.parquet")
    if sorted(set(m["day"])) != days:
        raise SystemExit(f"the run covers {sorted(set(m['day']))}, not the training days {days}")
    out = {"source": {"run": run_dir.name, "commit": meta["commit"], "days": days,
                      "cell": list(PRIMARY), "rule": "PREREGISTRATION.md section 4"}}  # fmt: skip
    tables = {}
    for name in ("B0", "B1"):
        table = candidate_table(m, name, days)
        pick = select(table, name)  # raises where section 4 has no rule
        out[name] = {k: v for k, v in pick["params"].items() if k != "name"}
        rows = table.sort("mean_bef_bps", descending=True).iter_rows(named=True)
        tables[name] = [
            {**{k: v for k, v in json.loads(r["params"]).items() if k != "name"},
             "mean_daily_bef_bps": round(r["mean_bef_bps"], 6)}
            for r in rows
        ]  # fmt: skip
        lines = [
            f"# {name} selection on the training days (M2)",
            "",
            f"Run {run_dir.name} (commit {meta['commit'][:7]}), primary cell {PRIMARY[0]} / {PRIMARY[1]},",
            f"{len(days)} days. Rule: highest mean daily break-even fee (PREREGISTRATION.md section 4).",
            "",
            "| Candidate | Mean daily BEF bp |",
            "|---|---|",
            *(f"| {json.dumps({k: v for k, v in t.items() if k != 'mean_daily_bef_bps'})} | {t['mean_daily_bef_bps']:.4f} |"
              for t in tables[name]),
            "",
            f"Chosen: {json.dumps(out[name])}",
        ]  # fmt: skip
        path = ROOT / "docs" / "selection" / f"{name}_train.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
    out["tables"] = tables
    target = ROOT / "configs" / "selected.yaml"
    target.write_text(
        "# B0 and B1 chosen on the training days by scripts/write_selected.py (M2, AC2.5).\n"
        "# B2, B2b and B3 are added in M4 from the validation tuning.\n"
        + yaml.safe_dump(out, sort_keys=False)
    )
    print(target, json.dumps({k: out[k] for k in ("B0", "B1")}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
