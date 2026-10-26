#!/usr/bin/env python3
"""Tables for docs/exploratory/glft.md: GLFT, the v1 B1, as an exploratory result
(PREREGISTRATION.md, Design history). Reads committed runs only; prints markdown.

  uv run python scripts/glft_report.py

Runs: ccbf1a18e770 (train_select_window: the GLFT grid on training days), 633a29217f4b
(train_chosen_window: the chosen GLFT in all 8 cells), a582f2864e78 (diag_train_touch:
GLFT beside the touch base, quote distances), 4de702fe5d20 (diag_val: quote distances on
validation days), b63a70c9a965 (tune_val: v1 overlays on GLFT) and 9eaa1b3d693c
(canaries_val_draft: v1 canaries).
"""

import json
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.venue import venue_for
from toxic_flow.eval import analysis

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ("risk_averse", "high")
RUNS = {"grid": ("ccbf1a18e770", "train_select_window"), "chosen": ("633a29217f4b", "train_chosen_window"),
        "train": ("a582f2864e78", "diag_train_touch"), "val": ("4de702fe5d20", "diag_val"),
        "tune": ("b63a70c9a965", "tune_val"), "canaries": ("9eaa1b3d693c", "canaries_val_draft")}  # fmt: skip


def load(key: str) -> tuple[pl.DataFrame, dict]:
    h, cfg = RUNS[key]
    meta = json.loads((ROOT / "results" / h / "meta.json").read_text())
    if meta["config"] != f"configs/runs/{cfg}.yaml":
        raise SystemExit(f"{h} is not {cfg}")
    return pl.read_parquet(ROOT / "results" / h / "metrics.parquet"), meta


def f(x, nd=3) -> str:
    return "none" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def primary(m: pl.DataFrame) -> pl.DataFrame:
    return m.filter((pl.col("queue") == PRIMARY[0]) & (pl.col("latency") == PRIMARY[1]))


def grid_table() -> list[str]:
    m, meta = load("grid")
    b1 = (
        primary(m)
        .filter(pl.col("strategy") == "B1")
        .with_columns(
            gamma=pl.col("params").map_elements(
                lambda p: json.loads(p)["gamma"], return_dtype=pl.Float64
            )
        )
    )
    # A day without fills has no BEF or markouts (NaN); such a window has no mean BEF.
    per = b1.with_columns(pl.col("mean_markout_1s_bps", "mean_markout_60s_bps").fill_nan(None)).group_by(
        "params", "gamma"
    ).agg(
        bef=pl.col("break_even_fee_bps").mean(), fills=pl.col("fills").median(),
        mk1=pl.col("mean_markout_1s_bps").mean(), mk60=pl.col("mean_markout_60s_bps").mean(),
    )  # fmt: skip
    t = per.with_columns(pl.col("bef").fill_nan(None)).group_by("gamma").agg(
        lo=pl.col("bef").min(), hi=pl.col("bef").max(), n=pl.col("bef").count(),
        fills=pl.col("fills").median(), mk1=pl.col("mk1").mean(), mk60=pl.col("mk60").mean(),
    ).sort("gamma")  # fmt: skip
    L = [f"Run {meta['config_hash']} (configs/runs/{RUNS['grid'][1]}.yaml, commit {meta['commit'][:7]}), "
         "12 training days, primary cell, full day. Each gamma has five windows (5, 10, 20, 40 and",
         "80 minutes); the BEF columns give the lowest and highest of their mean daily BEF, over the",
         "windows where it is defined (a window with a day without fills has none).", "",
         "| gamma | Windows with a mean BEF | Mean daily BEF bp, lowest | highest | Median daily fills | Markout 1 s bp | Markout 60 s bp |",
         "|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in t.iter_rows(named=True):
        L.append(
            f"| {r['gamma']:g} | {r['n']} of 5 | {f(r['lo'])} | {f(r['hi'])} | {f(r['fills'], 0)} | {f(r['mk1'])} | {f(r['mk60'])} |"
        )
    return L


def chosen_table() -> list[str]:
    m, meta = load("chosen")
    b1 = m.filter(pl.col("strategy") == "B1")
    L = [f"Run {meta['config_hash']} (configs/runs/{RUNS['chosen'][1]}.yaml, commit {meta['commit'][:7]}), "
         "gamma 0.4 and a 10-minute window, 12 training days. Means over days.", "",
         "| Queue model | Latency | Fills a day | Mean daily BEF bp | Markout 1 s bp | Markout 60 s bp | Days without fills |",
         "|---|---|---|---|---|---|---|"]  # fmt: skip
    for (q, lat), g in b1.group_by(["queue", "latency"], maintain_order=True):
        L.append(f"| {q} | {lat} | {f(float(g['fills'].mean()), 1)} | {f(float(g['break_even_fee_bps'].mean()))} | "
                 f"{f(float(g['mean_markout_1s_bps'].mean()))} | {f(float(g['mean_markout_60s_bps'].mean()))} | "
                 f"{int((g['fills'] == 0).sum())} |")  # fmt: skip
    return L


def distance_table() -> list[str]:
    L = ["| Day | Split | Mid at the mark | gamma 0.4: bid from mid, ticks | in bp | fills | gamma 0.2: ticks | fills |",
         "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    xs, ys = [], []
    for key in ("train", "val"):
        m, _ = load(key)
        for day in sorted(set(m["day"])):
            d = m.filter(pl.col("day") == day)
            a, b = d.filter(pl.col("label") == "B1"), d.filter(pl.col("label") == "B1_g0.2")
            mid, ticks = float(a["mark_mid"][0]), float(a["median_bid_dist_ticks"][0])
            bp = 1e4 * ticks * venue_for(day)["tick_size"] / mid
            xs.append(mid)
            ys.append(ticks)
            L.append(f"| {day} | {key} | {f(mid, 0)} | {f(ticks, 1)} | {f(bp, 2)} | {a['fills'][0]} | "
                     f"{f(float(b['median_bid_dist_ticks'][0]), 1)} | {b['fills'][0]} |")  # fmt: skip
    L += ["", f"Correlation across the 18 days between the mid and the gamma 0.4 distance in ticks: "
          f"{f(float(np.corrcoef(xs, ys)[0, 1]))}."]  # fmt: skip
    return L


def touch_table() -> list[str]:
    m, meta = load("train")
    p = primary(m)
    L = [f"Run {meta['config_hash']} (configs/runs/{RUNS['train'][1]}.yaml, commit {meta['commit'][:7]}), "
         "12 training days, primary cell. T0 is the join-the-touch base, which v2 adopted as B1.", "",
         "| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Markout 60 s bp |",
         "|---|---|---|---|---|"]  # fmt: skip
    for lab, name in (
        ("B1", "GLFT, gamma 0.4"),
        ("B1_g0.2", "GLFT, gamma 0.2"),
        ("T0", "Touch, skew 1 tick"),
    ):
        g = p.filter(pl.col("label") == lab)
        L.append(f"| {name} | {f(float(g['fills'].mean()), 0)} | {f(float(g['break_even_fee_bps'].mean()))} | "
                 f"{f(float(g['mean_markout_1s_bps'].mean()))} | {f(float(g['mean_markout_60s_bps'].mean()))} |")  # fmt: skip
    return L


def overlay_lines() -> list[str]:
    mt, meta_t = load("tune")
    mc, meta_c = load("canaries")
    L = [f"Runs {meta_t['config_hash']} (tune_val) and {meta_c['config_hash']} (canaries_val_draft), "
         "6 validation days, primary cell.", "",
         "| Overlay on GLFT | Best mean daily BEF bp | Its c, d | Worst mean daily BEF bp |",
         "|---|---|---|---|"]  # fmt: skip
    for name in ("B2", "B2b", "B3"):
        t = (mt.filter(pl.col("strategy") == name).group_by("params")
             .agg(bef=pl.col("break_even_fee_bps").mean()).sort("bef", descending=True))  # fmt: skip
        best = json.loads(t["params"][0])
        L.append(
            f"| {name} | {f(t['bef'][0])} | {best['c']:g}, {best['d']:g} | {f(t['bef'][-1])} |"
        )
    c = analysis.compare(mc, "C2", "B1")
    b1 = float(primary(mc).filter(pl.col("label") == "B1")["break_even_fee_bps"].mean())
    L += ["", f"B1 (GLFT) mean daily BEF on these days: {f(b1)} bp. C2 - B1: {f(c['mean'])} bp, "
          f"bootstrap [{f(c['bootstrap_ci'][0])}, {f(c['bootstrap_ci'][1])}], {c['n_positive']} of {c['n']} days above 0."]  # fmt: skip
    return L


def main() -> None:
    sections = [("Grid on the training days", grid_table), ("The chosen setting in all 8 cells", chosen_table),
                ("Distance from the mid and the price level", distance_table),
                ("GLFT beside the touch base", touch_table), ("v1 overlays and the oracle on GLFT", overlay_lines)]  # fmt: skip
    out = []
    for title, fn in sections:
        out += [f"## {title}", "", *fn(), ""]
    print("\n".join(out))


if __name__ == "__main__":
    main()
