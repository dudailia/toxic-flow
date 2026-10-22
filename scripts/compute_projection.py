#!/usr/bin/env python3
"""Compute projection for M4 and M5 from the M0 benchmark. Prints markdown for DATA_RECON.md.

Usage: uv run python scripts/compute_projection.py [free_ram_gib]

Assumptions, each printed with the table: a day-run costs the B0 loop time of 2024-01-01
scaled by that day's book-file size (event count grows with it); test days have the mean
train and val size because HEAD gives no size; B1 to B3 cost the same as B0 per day,
which is a lower bound until M2 and M3 time them.
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
    free_ram_gib = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    bench = json.loads((ROOT / "data" / "benchmark_m0.json").read_text())
    recon = json.loads((ROOT / "data" / "recon.json").read_text())

    book = {
        f["date"]: f["get_headers"]["content_length"]
        for f in recon["files"]
        if f["data_type"] == "incremental_book_L2" and "get_headers" in f
    }
    seconds_per_byte = bench["loop_wall_seconds"] / book[bench["date"]]
    mean_book = sum(book.values()) / len(book)
    split = {f["date"]: f["split"] for f in recon["files"]}
    day_cost = {
        s: sum(seconds_per_byte * b for d, b in book.items() if split[d] == s)
        / sum(1 for d in book if split[d] == s)
        for s in ("train", "val")
    }
    day_cost["test"] = seconds_per_byte * mean_book

    cores = bench["machine"]["cores"]
    rss_gib = bench["backtest_peak_rss_bytes"] / GIB
    usable = max(1, min(cores, int(free_ram_gib // rss_gib)))

    rows = [
        ("M4 tuning", sum(TUNING.values()) * VAL_DAYS, "val"),
        ("M4 canaries and B1 reference", (CANARY_RUNS + 1) * VAL_DAYS, "val"),
        ("M4 MDE, B2b and B3 on train days", 2 * TRAIN_DAYS, "train"),
        ("M5 strategies, all cells", len(STRATEGIES_M5) * CELLS * TEST_DAYS, "test"),
        ("M5 canaries, primary cell only", CANARY_RUNS * TEST_DAYS, "test"),
        # C3 is zero latency, so it has one run per queue model instead of eight cells.
        ("M5 canaries in every cell (upper case)", (4 * CELLS + 4) * TEST_DAYS, "test"),
    ]
    print(f"- loop cost: {bench['loop_wall_seconds']} s for {book[bench['date']]:,} book bytes")
    print(
        f"- mean seconds per day-run: train {day_cost['train']:.0f}, val {day_cost['val']:.0f}, "
        f"test {day_cost['test']:.0f} (test assumed at the train and val mean size)"
    )
    print(
        f"- peak RSS per run {rss_gib:.2f} GiB; free RAM assumed {free_ram_gib:.1f} GiB; "
        f"cores {cores}; usable parallel runs {usable}"
    )
    print()
    print(f"| Item | Day-runs | Core-hours | Wall-clock hours at {usable} parallel |")
    print("|---|---|---|---|")
    totals = {"M4": [0, 0.0], "M5": [0, 0.0]}
    for name, runs, s in rows:
        core_h = runs * day_cost[s] / 3600
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
