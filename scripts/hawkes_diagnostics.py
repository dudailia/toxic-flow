#!/usr/bin/env python3
"""docs/hawkes_fit.md: the pooled training fit, K, and the time-rescaling diagnostics of
that fit on each validation day (PREREGISTRATION.md section 5, SPEC.md AC3.4 and AC3.5).

Usage: uv run python scripts/hawkes_diagnostics.py
Reads docs/signals/train_constants.json (scripts/fit_signals.py) and the validation days'
events; writes docs/signals/hawkes_val_residuals.json and docs/hawkes_fit.md. The
diagnostics are reported whatever they show. Nothing here is tuned on validation days.
"""

import json
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import assert_allowed, load_splits
from toxic_flow.engine.run import utc_ns
from toxic_flow.events.market_orders import EVENTS
from toxic_flow.signals.hawkes_fit import residual_report

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["mu_b", "mu_s", "alpha_bb", "alpha_bs", "alpha_sb", "alpha_ss", "beta"]


def day_residuals(day: str, p: dict) -> dict:
    assert_allowed(day)
    ev = pl.read_parquet(EVENTS / f"{day}.parquet", columns=["exch_ts", "side"])
    t = (ev["exch_ts"].to_numpy() - utc_ns(day, "00:00:00")) / 1e9
    k = (ev["side"] == "s").to_numpy().astype(np.int64)
    order = np.argsort(t, kind="mergesort")
    mu = [p["mu_b"], p["mu_s"]]
    alpha = [[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]]
    return residual_report(t[order], k[order], mu, alpha, p["beta"])


def main() -> None:
    c = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    h, p = c["hawkes"], c["hawkes"]["params"]
    val = load_splits()["val"]
    val = [d for d in val if d not in excluded_days(val)]
    res = {d: day_residuals(d, p) for d in val}
    (ROOT / "docs" / "signals" / "hawkes_val_residuals.json").write_text(
        json.dumps({"params_from": "docs/signals/train_constants.json", "days": res}, indent=2)
        + "\n"
    )
    lines = [
        "# Hawkes fit on the training days, and diagnostics on the validation days",
        "",
        "Written by scripts/hawkes_diagnostics.py from docs/signals/train_constants.json",
        "(scripts/fit_signals.py) and docs/signals/hawkes_val_residuals.json. The fit pools",
        f"the {len(c['days'])} training days, each an independent realisation of one day, on",
        "exchange timestamps of collapsed market-order events (PREREGISTRATION.md section 5).",
        "",
        "## Fit",
        "",
        f"{h['n_events']:,} events. Log-likelihood {h['loglik']:.1f}. Converged: {h['converged']}.",
        f"Branching ratio (spectral radius of alpha / beta): {h['branching_ratio']:.4f}, which "
        + (
            "is below 1, so AC3.4 holds."
            if h["branching_ratio"] < 1
            else "is not below 1: AC3.4 fails and the study stops."
        ),
        "",
        "| Parameter | Estimate | Standard error |",
        "|---|---|---|",
        *(f"| {n} | {p[n]:.6g} | {h['se'][n]:.3g} |" for n in NAMES),
        "",
        "Units: mu and alpha per second, beta per second. alpha_kj is the jump in the",
        "intensity of type k after an event of type j (b buyer-initiated, s seller-initiated).",
        "",
        "Known limitation, stated in section 5: the baseline mu is constant over the day, so",
        "intraday seasonality is left to the excitation, which tends to inflate the branching",
        "ratio.",
        "",
        "## Constants K (training days)",
        "",
        "| Signal and parameter | K |",
        "|---|---|",
        *(f"| {n} | {v:.6f} |" for n, v in c["K"].items()),
        "",
        "C4_x10 and C4_x0.1 are the wrong-decay canaries, with their own K (Q25).",
        "",
        "## Time-rescaling diagnostics on the validation days (AC3.5)",
        "",
        "Under the fitted model each type's rescaled inter-event times are i.i.d. Exp(1):",
        "mean 1, and a KS test against Exp(1) that does not reject. Reported whatever they show.",
        "",
        "| Day | Type | Events | Mean | KS statistic | KS p-value |",
        "|---|---|---|---|---|---|",
    ]
    for d, r in res.items():
        for k, v in r.items():
            lines.append(
                f"| {d} | {k} | {v['n']:,} | {v['mean']:.4f} | {v['ks_statistic']:.4f} | {v['ks_pvalue']:.3g} |"
            )
    means = [v["mean"] for r in res.values() for v in r.values()]
    lo_m, hi_m = min(means), max(means)
    worst = max(v["ks_statistic"] for r in res.values() for v in r.values())
    lines += [
        "",
        f"Largest KS statistic: {worst:.4f}. With hundreds of thousands of events per day the",
        "KS test detects small departures, so the statistic is the more useful number; the",
        "constant baseline is the expected source of misfit.",
        "",
        f"Mean residual from {lo_m:.3f} to {hi_m:.3f}. A mean above 1 means the fitted model",
        "expected more events than the day had, so the training fit runs hot on these days.",
        "",
        "B2's K (OFI windows of 1, 5 and 30 s) is not computed: its input needs a replay of the",
        "whole book per day, which this machine has neither the disk nor the memory to hold",
        f"(K_not_computed in train_constants.json: {', '.join(c['K_not_computed']) or 'none'}).",
    ]
    (ROOT / "docs" / "hawkes_fit.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
