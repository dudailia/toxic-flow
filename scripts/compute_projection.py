#!/usr/bin/env python3
"""Compute projection for M4 and M5 from the M0 benchmark. Prints markdown for DATA_RECON.md.

Usage: uv run python scripts/compute_projection.py [free_ram_gib]
Without an argument, free RAM is the available memory recorded by the benchmark.

M0 has one measured day, so every day-run is costed at the 2024-01-01 loop time. Once M1
has recorded the size of every train and val file (AC1.6), each day can be scaled by its
size, and test days estimated from the train and val sizes; those figures are estimates.
B1 to B3 are costed like B0, a lower bound until M2 and M3 time them.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 2**30

# PREREGISTRATION.md section 4: tuning candidates on validation days, primary cell.
TUNING = {"B2": 27, "B2b": 27, "B3": 9}
CANARY_RUNS = 5  # C1, C2, C3, and C4 at beta x 10 and beta / 10
CELLS = 8  # 4 queue models x 2 latency settings
STRATEGIES_M5 = ("B1", "B2", "B2b", "B3")
VAL_DAYS, TRAIN_DAYS, TEST_DAYS = 6, 12, 16


def main() -> None:
    bench = json.loads((ROOT / "data" / "benchmark_m0.json").read_text())
    recorded = bench["available_ram_bytes_at_end"] / GIB
    free_ram_gib = float(sys.argv[1]) if len(sys.argv) > 1 else recorded
    day_s = bench["loop_wall_seconds"]

    cores = bench["machine"]["cores"]
    rss_gib = bench["backtest_peak_rss_bytes"] / GIB
    usable = max(1, min(cores, int(free_ram_gib // rss_gib)))

    rows = [
        ("M4 tuning", sum(TUNING.values()) * VAL_DAYS),
        ("M4 canaries and B1 reference", (CANARY_RUNS + 1) * VAL_DAYS),
        ("M4 MDE, B2b and B3 on train days", 2 * TRAIN_DAYS),
        ("M5 strategies, all cells", len(STRATEGIES_M5) * CELLS * TEST_DAYS),
        ("M5 canaries, primary cell only", CANARY_RUNS * TEST_DAYS),
        # C3 is zero latency, so it has one run per queue model instead of eight cells.
        ("M5 canaries in every cell (upper case)", (4 * CELLS + 4) * TEST_DAYS),
    ]
    print(
        f"- day-run cost: {day_s} s, the 2024-01-01 loop "
        f"({bench['raw_bytes']:,} raw bytes, {bench['events']:,} events), for every day"
    )
    print(
        f"- peak RSS per run {rss_gib:.2f} GiB; free RAM assumed {free_ram_gib:.1f} GiB; "
        f"cores {cores}; usable parallel runs {usable}"
    )
    print()
    print(f"| Item | Day-runs | Core-hours | Wall-clock hours at {usable} parallel |")
    print("|---|---|---|---|")
    totals = {"M4": [0, 0.0], "M5": [0, 0.0]}
    for name, runs in rows:
        core_h = runs * day_s / 3600
        print(f"| {name} | {runs} | {core_h:.1f} | {core_h / usable:.1f} |")
        if "upper" not in name:
            totals[name[:2]][0] += runs
            totals[name[:2]][1] += core_h
    for m, (runs, core_h) in totals.items():
        print(
            f"| {m} total (canaries primary cell) | {runs} | {core_h:.1f} | {core_h / usable:.1f} |"
        )


if __name__ == "__main__":
    main()
