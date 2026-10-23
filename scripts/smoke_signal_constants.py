#!/usr/bin/env python3
"""SMOKE: Hawkes fit and the constants K on one training day, to run the overlays end to end.

Usage: uv run python scripts/smoke_signal_constants.py 2024-01-01
Writes docs/smoke/signals_<date>.json. The pre-registered Hawkes fit pools the 12
training days and K comes from all of them (PREREGISTRATION.md section 5); these one-day
values are placeholders and stay out of PREREGISTRATION.md.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.split_lock import assert_allowed, split_of
from toxic_flow.engine.run import event_inputs, ofi_inputs
from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_fit import fit
from toxic_flow.signals.hawkes_online import hawkes_signal
from toxic_flow.signals.normalise import NORM_STEPS, k_constant, trailing_mean
from toxic_flow.signals.ofi import ofi_window

ROOT = Path(__file__).resolve().parents[1]
OFI_WINDOW_S, TAU_S = 5.0, 5.0


def utc_ns(day: str, hms: str) -> int:
    return int(datetime.fromisoformat(f"{day}T{hms}+00:00").timestamp()) * 10**9


def main(day: str) -> None:
    assert_allowed(day)
    if split_of(day) != "train":
        raise SystemExit("smoke constants come from a training day only")
    start = utc_ns(day, "00:00:00")
    events = pl.read_parquet(ROOT / "data" / "events" / f"{day}.parquet")
    t0 = time.perf_counter()
    times = (events["exch_ts"].to_numpy() - start) / 1e9  # the fit uses exchange time
    types = (events["side"] == "s").to_numpy().astype(np.int64)
    order = np.argsort(times, kind="mergesort")
    hawkes = fit([(times[order], types[order], 86_400.0)])
    fit_s = time.perf_counter() - t0

    grid = np.arange(start, utc_ns(day, "23:59:00"), 100_000_000, dtype=np.int64)
    quoting = grid >= utc_ns(day, "00:30:00")
    ev_ts, ev_side = event_inputs(day)
    ofi_ts, cum = ofi_inputs(day)
    p = hawkes["params"]
    mu = np.array([p["mu_b"], p["mu_s"]])
    alpha = np.array([[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]])
    a_by_signal = {
        "B2_ofi_5s": np.abs(ofi_window(ofi_ts, np.diff(cum), grid, OFI_WINDOW_S)),
        "B2b_ewma_5s": ewma_at(ev_ts, ev_side, grid, TAU_S)[1],
        "B3_hawkes": hawkes_signal(ev_ts, ev_side, grid, mu, alpha, p["beta"])[1],
    }
    k = {}
    for name, a in a_by_signal.items():
        abar = trailing_mean(a, NORM_STEPS)
        k[name] = round(k_constant(a[quoting], abar[quoting]), 6)

    out = {
        "date": day,
        "label": "smoke: one training day; placeholders, not the pre-registered fit",
        "hawkes": {**hawkes, "fit_seconds": round(fit_s, 1), "time": "exchange timestamps"},
        "K": k,
        "signal_parameters": {"ofi_window_s": OFI_WINDOW_S, "tau_s": TAU_S},
    }
    path = ROOT / "docs" / "smoke" / f"signals_{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
