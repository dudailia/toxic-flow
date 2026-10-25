#!/usr/bin/env python3
"""Tables for docs/M4_diagnosis.md (items 1 to 5), from the two exploratory diagnosis runs.

  uv run python scripts/m4_diagnosis.py --val results/<diag_val> --train results/<diag_train>

Prints markdown; the ranked "What I think is wrong" section is written by hand from it.
Everything here is exploratory: training and validation days only.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.eval import analysis

PRIMARY = ("risk_averse", "high")


def load(run: Path, config: str) -> tuple[pl.DataFrame, dict]:
    meta = json.loads((run / "meta.json").read_text())
    if meta["config"] != f"configs/runs/{config}.yaml":
        raise SystemExit(f"{run} is not {config}")
    return pl.read_parquet(run / "metrics.parquet"), meta


def f(x, nd=3) -> str:
    return "none" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def cmp_line(m, a, b, queue=PRIMARY[0], latency=PRIMARY[1]) -> str:
    c = analysis.compare(m, a, b, queue, latency)
    return (f"| {a} - {b} | {queue} / {latency} | {c['n']} | {f(c['mean'])} | "
            f"[{f(c['bootstrap_ci'][0])}, {f(c['bootstrap_ci'][1])}] | "
            f"[{f(c['t_ci'][0])}, {f(c['t_ci'][1])}] | {c['n_positive']} |")  # fmt: skip


CMP_HEAD = ["| Comparison | Cell | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |",
            "|---|---|---|---|---|---|---|"]  # fmt: skip

COLS = {
    "fills": "Fills a day",
    "break_even_fee_bps": "BEF bp",
    "mean_markout_1s_bps": "Markout 1 s bp",
    "mean_markout_10s_bps": "Markout 10 s bp",
    "mean_markout_60s_bps": "Markout 60 s bp",
    "cancels_per_hour": "Cancels an hour",
    "median_fill_wait_s": "Median order-to-fill s",
    "bid_at_best_share": "Bid at best",
    "ask_at_best_share": "Ask at best",
    "quote_presence": "Both sides resting",
    "median_bid_dist_ticks": "Bid from mid, ticks",
    "median_ask_dist_ticks": "Ask from mid, ticks",
}


def profile(m: pl.DataFrame, labels: list[str], cols: dict) -> list[str]:
    """Mean over days of each column, one row per label (primary cell unless the label
    lives in another cell)."""
    out = ["| Strategy | Days | " + " | ".join(cols.values()) + " |",
           "|---|---|" + "---|" * len(cols)]  # fmt: skip
    for lab in labels:
        r = m.filter(pl.col("label") == lab)
        out.append(f"| {lab} | {r['day'].n_unique()} | "
                   + " | ".join(f(float(r[c].mean()), 3) for c in cols) + " |")  # fmt: skip
    return out


def hourly(m: pl.DataFrame, label: str) -> pl.DataFrame:
    rows = []
    for day, js in m.filter(pl.col("label") == label).select("day", "hourly_quotes").iter_rows():
        for h in json.loads(js):
            rows.append({"day": day, **h})
    return (
        pl.DataFrame(rows)
        .group_by("hour")
        .agg(pl.col("bid_dist_ticks").median(), pl.col("ask_dist_ticks").median(),
             pl.col("fills").mean())
        .sort("hour")
    )  # fmt: skip


def main(val: Path, train: Path | None, window: Path | None) -> None:
    mv, meta_v = load(val, "diag_val")
    L = [f"Runs: validation {meta_v['config_hash']} (configs/runs/diag_val.yaml, commit "
         f"{meta_v['commit'][:7]}). Exploratory throughout.", ""]  # fmt: skip

    L += ["## 1. Sign check", "", *CMP_HEAD, cmp_line(mv, "C2", "B1"), cmp_line(mv, "C2_flip", "B1"),
          cmp_line(mv, "C2_flip", "C2"), ""]  # fmt: skip
    L += ["## 2. C2 against B1 in the easiest cell (log queue model, zero latency)", "",
          *CMP_HEAD, cmp_line(mv, "C2_easy", "B1_easy", "log", "zero"), "",
          *profile(mv, ["B1_easy", "C2_easy"], {k: COLS[k] for k in
                   ("fills", "break_even_fee_bps", "mean_markout_1s_bps", "mean_markout_10s_bps",
                    "mean_markout_60s_bps")}), ""]  # fmt: skip
    L += ["## 3. Why C2 loses: B1 and C2 on the validation days (primary cell)", "",
          "Mean over the 6 days. Markouts are per fill in our favour, averaged per day.",
          "Order-to-fill is from the order's request to its fill at the exchange. At best:",
          "share of decision steps with our target bid at or above the best bid (ask at or",
          "below the best ask).", "", *profile(mv, ["B1", "C2", "C2_flip"], COLS), ""]  # fmt: skip

    if train is None:
        L += part_4_without_train(mv, window)
        print("\n".join(L))
        return
    mt, meta_t = load(train, "diag_train_touch")
    L += ["## 4. Why B1 barely trades", "",
          *profile(pl.concat([mt.with_columns(pl.lit("train").alias("split")),
                              mv.with_columns(pl.lit("val").alias("split"))], how="diagonal_relaxed")
                   .with_columns((pl.col("label") + " " + pl.col("split")).alias("label")),
                   ["B1 train", "B1 val", "B1_g0.2 train", "B1_g0.2 val"],
                   {k: COLS[k] for k in ("fills", "break_even_fee_bps", "median_bid_dist_ticks",
                                         "median_ask_dist_ticks", "bid_at_best_share",
                                         "quote_presence")}), ""]  # fmt: skip
    L += ["Fills a day and the mid (USDT) by day, B1 at the selected setting:", "",
          "| Day | Split | B1 fills | B1_g0.2 fills | Mid at the mark | B1 bid from mid, ticks |",
          "|---|---|---|---|---|---|"]  # fmt: skip
    for split, m in (("train", mt), ("val", mv)):
        for day in sorted(set(m["day"])):
            d = m.filter(pl.col("day") == day)

            def g(lab, col, d=d):
                return d.filter(pl.col("label") == lab)[col][0]

            L.append(f"| {day} | {split} | {g('B1', 'fills')} | {g('B1_g0.2', 'fills')} | "
                     f"{f(g('B1', 'mark_mid'), 0)} | {f(g('B1', 'median_bid_dist_ticks'), 1)} |")  # fmt: skip
    L += ["", "B1 (selected) by UTC hour, median over days of the hourly median distance:", "",
          "| Hour | Train bid ticks | Train ask ticks | Train fills | Val bid ticks | Val ask ticks | Val fills |",
          "|---|---|---|---|---|---|---|"]  # fmt: skip
    ht, hv = hourly(mt, "B1"), hourly(mv, "B1")
    for a, b in zip(ht.iter_rows(named=True), hv.iter_rows(named=True), strict=False):
        L.append(f"| {a['hour']} | {f(a['bid_dist_ticks'], 1)} | {f(a['ask_dist_ticks'], 1)} | "
                 f"{f(a['fills'], 1)} | {f(b['bid_dist_ticks'], 1)} | {f(b['ask_dist_ticks'], 1)} | "
                 f"{f(b['fills'], 1)} |")  # fmt: skip

    L += ["", "## 5. Exploratory base on training days: join the touch (T0)", "",
          "T0 quotes at the best bid and ask with one tick of inventory skew per order size",
          "and the same cap; C2_touch is the oracle overlay (c = 1, m = 0) on it. Primary cell.",
          "", *profile(mt.filter(pl.col("queue").eq(PRIMARY[0]) & pl.col("latency").eq(PRIMARY[1])),
                       ["B1", "T0", "C2_touch"], COLS), "",
          *CMP_HEAD, cmp_line(mt, "C2_touch", "T0"), cmp_line(mt, "T0", "B1"), ""]  # fmt: skip
    print("\n".join(L))


def part_4_without_train(mv: pl.DataFrame, window: Path) -> list[str]:
    """Item 4 while the training diagnosis run is missing: fills a day on training days
    from the committed selection run (same B1 settings, primary cell), and the quote
    distance on validation days only."""
    mw, meta_w = load(window, "train_select_window")
    sel = {"B1": '"gamma": 0.4', "B1_g0.2": '"gamma": 0.2'}
    L = ["## 4. Why B1 barely trades (partial: the training diagnosis run did not finish)", "",
         f"Training-day fills from run {meta_w['config_hash']} (configs/runs/train_select_window.yaml),",
         "the same B1 settings in the same cell; distance from mid is measured on validation days",
         "only, because the instrumented training run stopped at the disk floor.", "",
         "| Strategy | Training fills a day (mean) | Training BEF bp | Validation fills a day | Validation BEF bp | Validation bid from mid, ticks |",
         "|---|---|---|---|---|---|"]  # fmt: skip
    for lab, key in sel.items():
        w = "600" if lab == "B1" else "1200"
        t = mw.filter(pl.col("strategy").eq("B1") & pl.col("params").str.contains(key)
                      & pl.col("params").str.contains(f'"window_s": {w}'))  # fmt: skip
        v = mv.filter(pl.col("label") == lab)
        L.append(f"| {lab} | {f(float(t['fills'].mean()), 1)} | {f(float(t['break_even_fee_bps'].mean()))} | "
                 f"{f(float(v['fills'].mean()), 1)} | {f(float(v['break_even_fee_bps'].mean()))} | "
                 f"{f(float(v['median_bid_dist_ticks'].mean()), 1)} |")  # fmt: skip
    L += ["", "Fills a day and the mid by day, B1 at the selected setting:", "",
          "| Day | Split | B1 fills | B1_g0.2 fills | Mid at the mark |", "|---|---|---|---|---|"]  # fmt: skip
    for day in sorted(set(mw["day"])):
        d = mw.filter(pl.col("day") == day)
        a = d.filter(
            pl.col("params").str.contains('"gamma": 0.4')
            & pl.col("params").str.contains('"window_s": 600')
        )
        b = d.filter(
            pl.col("params").str.contains('"gamma": 0.2')
            & pl.col("params").str.contains('"window_s": 1200')
        )
        L.append(
            f"| {day} | train | {a['fills'][0]} | {b['fills'][0]} | {f(float(a['mark_mid'][0]), 0)} |"
        )
    for day in sorted(set(mv["day"])):
        d = mv.filter(pl.col("day") == day)
        a, b = d.filter(pl.col("label") == "B1"), d.filter(pl.col("label") == "B1_g0.2")
        L.append(
            f"| {day} | val | {a['fills'][0]} | {b['fills'][0]} | {f(float(a['mark_mid'][0]), 0)} |"
        )
    L += [
        "",
        "B1 (selected) on validation days by UTC hour, median over days:",
        "",
        "| Hour | Bid from mid, ticks | Ask from mid, ticks | Fills (mean) |",
        "|---|---|---|---|",
    ]
    for r in hourly(mv, "B1").iter_rows(named=True):
        L.append(
            f"| {r['hour']} | {f(r['bid_dist_ticks'], 1)} | {f(r['ask_dist_ticks'], 1)} | {f(r['fills'], 2)} |"
        )
    L += [
        "",
        "## 5. Exploratory touch base on training days",
        "",
        "Not done: the training run (configs/runs/diag_train_touch.yaml) stopped at the disk floor",
        "after 173 of 564 cells and wrote no metrics. See docs/SESSION_REPORT.md.",
        "",
    ]
    return L


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--val", type=Path, required=True)
    p.add_argument("--train", type=Path)
    p.add_argument("--window", type=Path, help="train_select_window run, when --train is missing")
    a = p.parse_args()
    main(a.val, a.train, a.window)
