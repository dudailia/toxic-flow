#!/usr/bin/env python3
"""SMOKE: time-rescaling residuals and KS of the one-day Hawkes fit, on the same day.

Usage: uv run python scripts/smoke_hawkes_residuals.py 2024-01-01
Reads docs/smoke/signals_<date>.json, writes docs/smoke/hawkes_residuals_<date>.json.
In-sample on the fitted day, so it checks the code path, not the model; AC3.5 asks for
validation days with the pooled training fit.
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.split_lock import assert_allowed
from toxic_flow.signals.hawkes_fit import residual_report

ROOT = Path(__file__).resolve().parents[1]


def main(day: str) -> None:
    assert_allowed(day)
    p = json.loads((ROOT / "docs" / "smoke" / f"signals_{day}.json").read_text())["hawkes"][
        "params"
    ]
    events = pl.read_parquet(ROOT / "data" / "events" / f"{day}.parquet")
    start = int(np.datetime64(f"{day}T00:00:00", "ns").astype(np.int64))
    times = (events["exch_ts"].to_numpy() - start) / 1e9
    types = (events["side"] == "s").to_numpy().astype(np.int64)
    order = np.argsort(times, kind="mergesort")
    mu = [p["mu_b"], p["mu_s"]]
    alpha = [[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]]
    report = {
        "date": day,
        "label": "smoke: in-sample on the fitted day; not the AC3.5 validation-day check",
        "residuals": residual_report(times[order], types[order], mu, alpha, p["beta"]),
    }
    out = ROOT / "docs" / "smoke" / f"hawkes_residuals_{day}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
