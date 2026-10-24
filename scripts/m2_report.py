#!/usr/bin/env python3
"""AC2.4 table: fills per queue model for each training day and latency, from a run's
metrics.parquet only (SPEC.md M2).

Usage: uv run python scripts/m2_report.py results/<hash> docs/m2_fills.md

For each strategy, day and latency it lists the fills under the four queue models and
whether the risk-averse model has no more fills than any other. AC2.4 asks this for B1
on every training day and latency; if it fails, the pessimistic reference is not pessimistic
and M2 stops. A tie at the minimum passes (Ilia, Q42, 2026-10-24): the point is that
risk-averse is never more optimistic than the others. Rows where it is alone with the
fewest are counted too, for the record.
"""

import json
import sys
from pathlib import Path

import polars as pl

QUEUES = ["risk_averse", "power3", "power2", "log"]


def main(run_dir: Path, out: Path) -> None:
    meta = json.loads((run_dir / "meta.json").read_text())
    m = pl.read_parquet(run_dir / "metrics.parquet")
    lines = [
        f"# Fills per queue model on the training days (AC2.4), run {meta['config_hash']}",
        "",
        f"Config {meta['config']}; commit {meta['commit'][:7]}; hftbacktest {meta['hftbacktest']}.",
        "From metrics.parquet by scripts/m2_report.py. Fewest: the queue model(s) with the",
        "smallest fill count. AC2.4 needs risk_averse to have no more fills than any other",
        "queue model for B1 on every day and latency; a tie passes (Q42).",
        "",
        "| Strategy | Day | Latency | " + " | ".join(QUEUES) + " | Fewest | Risk-averse no more |",
        "|---|---|---|" + "---|" * len(QUEUES) + "---|---|",
    ]
    verdict, alone = {}, {}
    for (s, day, lat), g in m.sort(["strategy", "day", "latency"]).group_by(
        ["strategy", "day", "latency"], maintain_order=True
    ):
        fills = {q: int(g.filter(pl.col("queue") == q)["fills"][0]) for q in QUEUES}
        low = min(fills.values())
        fewest = [q for q in QUEUES if fills[q] == low]
        ok = fills["risk_averse"] == low
        verdict.setdefault(s, []).append(ok)
        alone.setdefault(s, []).append(fewest == ["risk_averse"])
        lines.append(
            f"| {s} | {day} | {lat} | " + " | ".join(str(fills[q]) for q in QUEUES)
            + f" | {' = '.join(fewest)} | {'yes' if ok else 'no'} |"
        )  # fmt: skip
    lines += [""] + [
        f"{s}: risk-averse has no more fills than any other queue model in {sum(v)} of {len(v)}"
        f" day and latency rows, and is alone with the fewest in {sum(alone[s])}."
        for s, v in verdict.items()
    ]
    b1 = verdict.get("B1", [])
    lines.append(
        "AC2.4 holds for B1." if b1 and all(b1) else "AC2.4 does not hold for B1: M2 stops here."
    )
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-len(verdict) - 1 :]))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
