#!/usr/bin/env python3
"""Signal constants from the training days (PREREGISTRATION.md section 5).

  uv run python scripts/fit_signals.py           all non-excluded training days
  uv run python scripts/fit_signals.py --smoke   only the training days on disk, as SMOKE

Pools the Hawkes fit over the days (exchange timestamps, each day an independent
realisation) and computes K, the 99th percentile of a / abar - 1 over the quoting
windows of all the days, for every signal and parameter of the tuning grid: B2 at
W = 1, 5, 30 s, B2b at tau = 1, 5, 30 s, B3 at the fitted beta. K is also reported for
the C4 variants (beta and alpha x10 and x0.1) so Q25 can be settled with numbers.
abar is the trailing 30-minute mean within each day, as in the strategy loop.
Writes docs/signals/train_constants.json, or docs/smoke/train_constants_smoke.json.
AC3.4: if the fitted branching ratio is not below 1, the study stops; the script says so
and exits 1 after writing the file.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.convert import CONVERTED
from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import assert_allowed, load_splits
from toxic_flow.engine.run import event_inputs, ofi_inputs, utc_ns
from toxic_flow.events.market_orders import EVENTS
from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_fit import fit, rescale_decay
from toxic_flow.signals.hawkes_online import hawkes_signal
from toxic_flow.signals.normalise import NORM_STEPS, k_constant, trailing_mean
from toxic_flow.signals.ofi import ofi_window

ROOT = Path(__file__).resolve().parents[1]
OFI_WINDOWS_S = (1.0, 5.0, 30.0)  # section 4 tuning grid
TAUS_S = (1.0, 5.0, 30.0)
C4_FACTORS = (10.0, 0.1)  # section 10
STEP_NS = 100_000_000
QUOTE_START = "00:30:00"  # as in every run config
DAY_S = 86_400.0


def hawkes_arrays(p: dict):
    mu = np.array([p["mu_b"], p["mu_s"]])
    alpha = np.array([[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]])
    return mu, alpha, p["beta"]


def day_ratios(day: str, params: dict, with_ofi: bool) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(a, abar) over the day's quoting window for every signal and parameter; B2 only
    with_ofi, since its input needs a replay of the whole book."""
    start = utc_ns(day, "00:00:00")
    grid = np.arange(start, utc_ns(day, "23:59:00"), STEP_NS, dtype=np.int64)
    quoting = grid >= utc_ns(day, QUOTE_START)
    ev_ts, ev_side = event_inputs(day)
    a = {}
    if with_ofi:
        ofi_ts, cum = ofi_inputs(day)
        a = {
            f"B2_ofi_{w:g}s": np.abs(ofi_window(ofi_ts, np.diff(cum), grid, w))
            for w in OFI_WINDOWS_S
        }
    a |= {f"B2b_ewma_{t:g}s": ewma_at(ev_ts, ev_side, grid, t)[1] for t in TAUS_S}
    a["B3_hawkes"] = hawkes_signal(ev_ts, ev_side, grid, *hawkes_arrays(params))[1]
    for f in C4_FACTORS:
        p = rescale_decay(params, f)
        a[f"C4_x{f:g}"] = hawkes_signal(ev_ts, ev_side, grid, *hawkes_arrays(p))[1]
    return {k: (v[quoting], trailing_mean(v, NORM_STEPS)[quoting]) for k, v in a.items()}


def fit_days(days: list[str]) -> dict:
    """Pooled fit on exchange timestamps of the collapsed events (section 5)."""
    sets = []
    for day in days:
        ev = pl.read_parquet(EVENTS / f"{day}.parquet", columns=["exch_ts", "side"])
        t = (ev["exch_ts"].to_numpy() - utc_ns(day, "00:00:00")) / 1e9
        k = (ev["side"] == "s").to_numpy().astype(np.int64)
        order = np.argsort(t, kind="mergesort")
        sets.append((t[order], k[order], DAY_S))
    t0 = time.perf_counter()
    out = fit(sets)
    return {**out, "fit_seconds": round(time.perf_counter() - t0, 1), "time": "exchange timestamps"}


def main(smoke: bool) -> int:
    train = load_splits()["train"]
    days = [d for d in train if d not in excluded_days(train)]
    # A day is ready once its market-order events exist. B2's input, the OFI
    # contributions, needs a replay of the whole book; unless every day has it, B2's K is
    # left out and said so.
    on_disk = [d for d in days if (EVENTS / f"{d}.parquet").exists()]
    with_ofi = all((CONVERTED / d / "ofi_contributions.npz").exists() for d in on_disk)
    if not smoke and on_disk != days:
        missing = sorted(set(days) - set(on_disk))
        raise SystemExit(f"{len(missing)} training days not on disk: {missing}; use --smoke")
    days = on_disk
    for d in days:
        assert_allowed(d)
    hawkes = fit_days(days)
    ratios = [day_ratios(d, hawkes["params"], with_ofi) for d in days]
    k = {
        name: round(k_constant(np.concatenate([r[name][0] for r in ratios]),
                               np.concatenate([r[name][1] for r in ratios])), 6)
        for name in ratios[0]
    }  # fmt: skip
    stop = not hawkes["branching_ratio"] < 1
    out = {
        "label": "SMOKE: training days on disk only, not the pre-registered fit"
        if smoke
        else "train",
        "days": days,
        "hawkes": hawkes,
        "K": k,
        "K_not_computed": [] if with_ofi else [f"B2_ofi_{w:g}s" for w in OFI_WINDOWS_S],
        "ac3_4_branching_ratio_below_1": not stop,
    }
    path = ROOT / (
        "docs/smoke/train_constants_smoke.json" if smoke else "docs/signals/train_constants.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {k_: v for k_, v in out.items() if k_ != "hawkes"} | {"path": str(path)}, indent=2
        )
    )
    if stop:
        print(
            "AC3.4 fails: branching ratio not below 1. The study stops; revise section 5 before the tag."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main("--smoke" in sys.argv[1:]))
