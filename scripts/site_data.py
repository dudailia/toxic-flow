#!/usr/bin/env python3
"""The data bundle for the project page on iliaduda.com: site/toxic-flow.json.

Usage: uv run python scripts/site_data.py   (make site-data)

Built only from committed files: the results/<hash>/metrics.parquet of the runs the paper
already reports (paper/pre_test.py RUNS) and the committed outputs of the fitting scripts
(docs/signals, docs/exploratory). The script refuses a source that git does not track or
that differs from the commit. Each section lists its sources, so every number can be
traced to one (tests/unit/test_site.py rebuilds the bundle and compares). Numbers are
unformatted. The test-day block is read from the committed results/summary.json, every
key the paper takes from it. Fills are simulated.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper"))
sys.path.insert(0, str(ROOT / "scripts"))

import pre_test  # noqa: E402
from m4_v2 import kept, matched_pairs, tune_runs  # noqa: E402

from toxic_flow.data.split_lock import load_splits  # noqa: E402
from toxic_flow.engine.configs import quote_hours  # noqa: E402
from toxic_flow.eval import analysis  # noqa: E402
from toxic_flow.eval.bootstrap import STATEMENTS  # noqa: E402

OUT = ROOT / "site" / "toxic-flow.json"
PRIMARY = analysis.PRIMARY
CELLS = [f"{q}/{lat}" for q, lat in analysis.CELLS]
RUNS = pre_test.RUNS

# The design history (PREREGISTRATION.md, Design history) as dated events, each with the
# commit that made it. tests/unit/test_site.py checks every hash and its commit date.
TIMELINE = [
    ("2026-10-22", "282ddbf", "v1 pre-registration drafted: fixed-spread B0, GLFT B1, an overlay that shifts the GLFT quote centre"),
    ("2026-10-24", "3dd1451", "v1 fails canary C2 on the validation days: the oracle loses to B1, so that harness cannot turn information into PnL"),
    ("2026-10-25", "962451d", "v2 chosen by Ilia Duda before any test-day download: quote at the touch, step back on the side the signal marks toxic"),
    ("2026-10-26", "b4ac010", "C1 pass rule revised after C1 failed against B1: C1 is judged against R1, random pulls at C1's rate"),
    ("2026-10-26", "c250c3e", "Settings, thresholds, s and the MDE filled in from committed results"),
    ("2026-10-26", "75f45c0", "Run-length controls RL_B3 and RL_B2b added (exploratory)"),
    ("2026-10-26", "681b212", "Fill-hold control F added (exploratory), its hold rule committed before F ran"),
    ("2026-10-26", "2ae88eb", "F's hold chosen on the training days: 0.1 s"),
    ("2026-10-26", "4f6a1c5", "Wording settled: no-print fills (section 3), selectivity (section 8), canary intervals (section 10), intervals that disagree (section 11)"),
    ("2026-10-26", "36e0bb7", "C3 flag revised after the M5 dress rehearsal showed it firing on noise"),
    ("2026-10-26", "1aca2b4", "Markout clock stated in section 6"),
]  # fmt: skip


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


def committed(rel: str) -> str:
    """rel, after checking that git tracks it and the file equals the version in git's index.
    A staged change counts as committed: the pre-commit hook builds the bundle while the
    change is staged, so the bundle is checked against what the commit will hold."""
    if not git("ls-files", "--", rel).strip():
        raise SystemExit(f"{rel} is not tracked by git: the bundle reads committed files only")
    # Porcelain "XY path": Y is the working copy against the index.
    if git("status", "--porcelain", "--", rel)[1:2].strip():
        raise SystemExit(f"{rel} differs from the commit")
    return rel


def run_source(name: str) -> str:
    return committed(f"results/{RUNS[name]}/metrics.parquet")


def num(x) -> float | None:
    x = float(x)
    return x if np.isfinite(x) else None


def comparison(m, a, b, source, label, queue=PRIMARY[0], latency=PRIMARY[1]) -> dict:
    c = analysis.compare(m, a, b, queue, latency)
    return {"a": a, "b": b, "cell": f"{queue}/{latency}", "label": label, "source": source,
            "n_days": c["n"], "days_dropped": c["dropped"], "mean_bp": num(c["mean"]),
            "bootstrap_ci_bp": [num(x) for x in c["bootstrap_ci"]],
            "t_ci_bp": [num(x) for x in c["t_ci"]], "days_positive": c["n_positive"],
            "per_day_bp": {d: num(v) for d, v in c["per_day"].items()}}  # fmt: skip


def strategies(m: pl.DataFrame, source: str, hours: float) -> dict:
    """Per label in the primary cell: means over days and the value on each day."""
    p = pre_test.primary(analysis.with_seed_means(m))
    out = {}
    for (lab,), g in sorted(p.group_by("label"), key=lambda x: x[0]):
        g = g.sort("day")
        cols = {"bef_bp": "break_even_fee_bps", "fills": "fills",
                "markout_1s_bp": "mean_markout_1s_bps", "markout_60s_bp": "mean_markout_60s_bps",
                "toxic_share": "toxic_share"}  # fmt: skip
        cols = {k: c for k, c in cols.items() if c in g.columns and g[c].null_count() < g.height}
        out[lab] = {"source": source,
                    "mean": {k: num(g[c].mean()) for k, c in cols.items()},
                    "per_day": {d: {k: num(g[c][i]) for k, c in cols.items()}
                                for i, d in enumerate(g["day"])}}  # fmt: skip
        if "toxic_episodes" in g.columns and g["toxic_episodes"].null_count() == 0:
            out[lab]["mean"]["pulled_runs_per_hour"] = num(g["toxic_episodes"].mean() / hours)
    return out


def validation() -> dict:
    sources = {k: run_source(k) for k in ("v2_canaries_val", "v2_random_pulls_val",
                                          "v2_run_length_val", "v2_fill_hold_val")}  # fmt: skip
    mc = pre_test.run("v2_canaries_val")
    rp = analysis.with_seed_means(pre_test.run("v2_random_pulls_val"))
    rl = analysis.with_seed_means(pre_test.run("v2_run_length_val"))
    f = pl.concat([pre_test.run("v2_fill_hold_val"), rl.filter(pl.col("strategy") == "RL")],
                  how="diagonal_relaxed")  # fmt: skip
    can, ran, rlen, fh = (sources[k] for k in sources)
    rows = [
        (mc, "B3", "B1", can, "exploratory, H3 on validation days"),
        (mc, "B2b", "B1", can, "exploratory, H4 on validation days"),
        (mc, "B3", "B2b", can, "H1's statistic on validation days, not the test"),
        (mc, "C2", "B1", can, "canary C2, oracle"),
        (mc, "C1", "B1", can, "canary C1, the rule first written"),
        (mc, "C1", "B3", can, "canary C1, descriptive"),
        (mc, "C4_x10", "B3", can, "canary C4, decay x10"),
        (mc, "C4_x0.1", "B3", can, "canary C4, decay x0.1"),
        (rp, "C1", "R1", ran, "canary C1, the revised rule"),
        (rp, "R1", "B1", ran, "control, random pulls at C1's rate"),
        (rp, "B3", "R_B3", ran, "exploratory, random pulls at B3's rate"),
        (rp, "B2b", "R_B2b", ran, "exploratory, random pulls at B2b's rate"),
        (rl, "B3", "RL_B3", rlen, "exploratory, random pulls matched on rate and pulled runs"),
        (rl, "B2b", "RL_B2b", rlen, "exploratory, random pulls matched on rate and pulled runs"),
        (f, "B3", "F", f"{fh}, {rlen}", "exploratory, control F"),
        (f, "F", "RL_B3", f"{fh}, {rlen}", "exploratory, control F"),
    ]
    b3 = mc.filter(
        (pl.col("label") == "B3") & (pl.col("queue") == PRIMARY[0]) & (pl.col("fills") > 0)
    )
    c3 = {lat: num(b3.filter(pl.col("latency") == lat)["break_even_fee_bps"].mean())
          for lat in ("zero", "high")}  # fmt: skip
    hours = quote_hours()
    return {
        "days": kept("val"),
        "comparisons": [comparison(m, a, b, s, lab) for m, a, b, s, lab in rows],
        "c3_mean_bef_bp": {"source": can, "risk_averse": c3},
        "strategies": {"v2_canaries_val": strategies(mc, can, hours),
                       "v2_random_pulls_val": strategies(pre_test.run("v2_random_pulls_val"), ran, hours),
                       "v2_run_length_val": strategies(pre_test.run("v2_run_length_val"), rlen, hours),
                       "v2_fill_hold_val": strategies(pre_test.run("v2_fill_hold_val"), fh, hours)},
    }  # fmt: skip


def grid(m: pl.DataFrame, labels, source: str) -> dict:
    """Mean BEF of each label in each of the 8 queue and latency cells."""
    out = {"source": source}
    for lab in labels:
        g = m.filter(pl.col("label") == lab)
        out[lab] = {f"{q}/{lat}": num(g.filter((pl.col("queue") == q) & (pl.col("latency") == lat))
                                      ["break_even_fee_bps"].mean())
                    for q, lat in analysis.CELLS}  # fmt: skip
    return out


def training() -> dict:
    tr, mde_run, gl = (
        run_source("v2_train"),
        run_source("v2_mde_train"),
        run_source("train_chosen_window"),
    )
    m = pre_test.run("v2_train").with_columns(label=pl.col("strategy"))
    return {
        "days": kept("train"),
        "grids": {
            "B0_B1_mean_bef_bp": grid(m, ("B0", "B1"), tr),
            "B1_minus_B0": {"source": tr, **{f"{q}/{lat}": comparison(m, "B1", "B0", tr, "descriptive", q, lat)
                                             for q, lat in analysis.CELLS}},
            "glft_v1_mean_bef_bp": grid(pre_test.run("train_chosen_window").filter(pl.col("strategy") == "B1"),
                                        ("B1",), gl),
        },
        "comparisons": [comparison(pre_test.run("v2_mde_train"), "B3", "B2b", mde_run,
                                   "H1's statistic on training days, for s")],
        "strategies": {"v2_train": strategies(m, tr, quote_hours())},
    }  # fmt: skip


def mde() -> dict:
    x = analysis.mde_inputs(pre_test.run("v2_mde_train"), pre_test.run("v2_canaries_val"),
                            len(kept("test")))  # fmt: skip
    return {"source": [run_source("v2_mde_train"), run_source("v2_canaries_val")],
            "s_train_bp": x["s_train_bp"], "s_val_bp": x["s_val_bp"], "s_bp": x["s_bp"],
            "mde_bp": x["mde_bp"], "c2_threshold_bp": 3 * x["mde_bp"], "n_test": x["n_test"],
            "formula": "MDE = (z_0.975 + z_0.80) * s / sqrt(n)"}  # fmt: skip


def matched_p() -> dict:
    src = [run_source("v2_tune_val_a"), run_source("v2_tune_val_b")]
    mt, _ = tune_runs([ROOT / "results" / RUNS[c] for c in ("v2_tune_val_a", "v2_tune_val_b")])
    rows = [{"p": p, **comparison(both, "B3", "B2b", ", ".join(src), "exploratory, same pull rate")}
            for p, both in matched_pairs(mt, pre_test.selected()).items()]  # fmt: skip
    return {"source": src, "rows": rows}


def hawkes() -> dict:
    src = committed("docs/signals/train_constants.json")
    c = json.loads((ROOT / src).read_text())["hawkes"]
    return {"source": src, "params": c["params"], "se": c["se"], "loglik": c["loglik"],
            "n_events": c["n_events"], "branching_ratio": c["branching_ratio"],
            "memory_ms": 1000 / c["params"]["beta"], "time": c["time"]}  # fmt: skip


def signal_information() -> dict:
    src = committed("docs/exploratory/signal_information.json")
    d = json.loads((ROOT / src).read_text())
    return {"source": src, "note": d["note"], "splits": d["splits"]}


def glft() -> dict:
    """v1's GLFT B1 (exploratory): fills against edge as gamma rises, the chosen setting,
    and its distance from the mid against the price."""
    src = [run_source(k) for k in ("train_select_window", "train_chosen_window",
                                   "diag_train_touch", "diag_val", "v2_train")]  # fmt: skip
    g = pre_test.primary(pre_test.run("train_select_window")).filter(pl.col("strategy") == "B1")
    g = g.with_columns(gamma=pl.col("params").map_elements(lambda s: json.loads(s)["gamma"],
                                                           return_dtype=pl.Float64))  # fmt: skip
    per = g.group_by("params", "gamma").agg(bef=pl.col("break_even_fee_bps").mean(),
                                            fills=pl.col("fills").median())  # fmt: skip
    by = per.group_by("gamma").agg(pl.col("bef").max(), pl.col("fills").median()).sort("gamma")
    c = pre_test.primary(pre_test.run("train_chosen_window")).filter(pl.col("strategy") == "B1")
    points = []
    for config in ("diag_train_touch", "diag_val"):
        b1 = pre_test.run(config).filter(pl.col("label") == "B1")
        points += [{"day": d, "mid": num(x), "median_bid_dist_ticks": num(y)}
                   for d, x, y in zip(b1["day"], b1["mark_mid"], b1["median_bid_dist_ticks"],
                                      strict=True)]  # fmt: skip
    xs = [p["mid"] for p in points]
    ys = [p["median_bid_dist_ticks"] for p in points]
    touch = pre_test.primary(pre_test.run("v2_train")).filter(pl.col("strategy") == "B1")
    return {"source": src, "label": "exploratory, v1",
            "by_gamma": [{"gamma": r["gamma"], "best_mean_bef_bp": num(r["bef"]),
                          "median_fills": num(r["fills"])} for r in by.iter_rows(named=True)],
            "chosen_gamma": json.loads(c["params"][0])["gamma"],
            "chosen_mean_bef_bp": num(c["break_even_fee_bps"].mean()),
            "chosen_mean_fills": num(c["fills"].mean()),
            "touch_b1_mean_fills": num(touch["fills"].mean()),
            "mid_vs_distance": points, "mid_distance_corr": num(np.corrcoef(xs, ys)[0, 1])}  # fmt: skip


def fill_hold() -> dict:
    """F's hold (configs/selected.yaml, the training-day rule) and its pull share against
    B3's, on the training days (where the rule matched them) and the validation days."""
    hold = pre_test.selected()["F"]["hold_s"]
    train_f = pre_test.run("v2_fill_hold_train").filter(pl.col("label") == f"F_h{hold:g}")
    train_b3 = pre_test.primary(pre_test.run("v2_mde_train")).filter(pl.col("label") == "B3")
    val = pre_test.primary(pre_test.run("v2_fill_hold_val"))
    share = lambda g: num(g["toxic_share"].mean())  # noqa: E731
    return {"source": [run_source("v2_fill_hold_train"), run_source("v2_mde_train"),
                       run_source("v2_fill_hold_val"), committed("configs/selected.yaml")],
            "hold_s": hold,
            "pull_share": {"train": {"F": share(train_f), "B3": share(train_b3)},
                           "val": {"F": share(val.filter(pl.col("label") == "F")),
                                   "B3": share(val.filter(pl.col("label") == "B3"))}}}  # fmt: skip


def conclusions() -> dict:
    """Section 11's pre-committed sentences, with the key the analysis code uses for each."""
    src = committed("PREREGISTRATION.md")
    table = (ROOT / src).read_text().split("## 11.")[1].split("## 12.")[0]
    rows = [[c.strip() for c in line.split("|")[1:3]] for line in table.splitlines()
            if line.startswith("|") and not line.startswith("|--")][1:]  # fmt: skip
    keys = {v.format(mean="X", lo="L", hi="U", mde="MDE"): k for k, v in STATEMENTS.items()}
    # The C1 row's sentence is printed by eval/analysis.canaries, not from STATEMENTS.
    keys["The signal's gain does not depend on event signs, so it is not order-flow "
         "information. Primary result reported but not interpreted."] = "c1_fails"  # fmt: skip
    return {"source": src, "rows": [{"outcome": o, "statement": s, "key": keys[s]}
                                    for o, s in rows]}  # fmt: skip


def test_keys() -> dict:
    """Every number the paper takes from the test days, read from the committed
    results/summary.json (scripts/analyse.py summary over the two M5 runs), with the label
    of the post-hoc numbers (DEVIATIONS.md entry 6)."""
    src = committed("results/summary.json")
    s = json.loads((ROOT / src).read_text())
    template = (ROOT / committed("paper/template.md")).read_text()
    keys = sorted({k for k in re.findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", template)
                   if not k.startswith("pre_")})  # fmt: skip
    per_day = s["h1"]["primary"]["per_day"]
    return {"source": src, "note": "Test days, from results/summary.json. Fills are simulated.",
            "runs": s["runs"], "keys": {k: s[k] for k in keys},
            "posthoc_note": s["posthoc_note"],
            "h1_cell_means_bp": s["h1"]["cell_means"],
            "h1_per_day_bp": {d: per_day[d] for d in load_splits()["test"]},
            "no_print_share": s["no_print_share"]}  # fmt: skip


def timeline() -> list[dict]:
    return [{"date": d, "commit": h, "event": e} for d, h, e in TIMELINE] + [
        {"date": None, "commit": None, "event": "Tag prereg-v1 created and pushed by Ilia Duda"}
    ]


V1_LABEL = "v1 design, superseded; failed canary C2"


def v1() -> dict:
    """v1's oracle canary C2 against its GLFT B1 on the validation days, primary cell, from
    the committed v1 canary run that docs/M4_draft.md reports. The failure that led to v2
    (Design history)."""
    src = run_source("canaries_val_draft")
    c2 = comparison(pre_test.run("canaries_val_draft"), "C2", "B1", src, V1_LABEL)
    return {"label": V1_LABEL, "source": src, "c2_minus_b1": c2}


def build() -> dict:
    splits = load_splits()
    return {
        "title": "Does a Hawkes model of order flow help a market maker? A pre-registered test",
        "note": "Replay simulation of historical Binance BTCUSDT perpetual data: simulated "
        "fills, no order sent to an exchange, no claim about live trading or profit. "
        "Test-day values come from results/summary.json.",
        "units": {"bp": "basis points of traded notional", "bef": "break-even maker fee"},
        "primary_cell": "/".join(PRIMARY),
        "cells": CELLS,
        "splits": {k: [str(d) for d in splits[k]] for k in ("train", "val", "test")},
        "runs": {
            k: {"hash": h, "source": f"results/{h}/metrics.parquet"}
            for k, h in sorted(RUNS.items())
        },  # fmt: skip
        "design_history": timeline(),
        "preregistered_conclusions": conclusions(),
        "hawkes_fit": hawkes(),
        "mde": mde(),
        "training": training(),
        "validation": validation(),
        "matched_p": matched_p(),
        "fill_hold": fill_hold(),
        "signal_information": signal_information(),
        "glft": glft(),
        "v1": v1(),
        "test": test_keys(),
    }


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n")
    print(OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
