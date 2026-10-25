#!/usr/bin/env python3
"""Tables for docs/exploratory/touch_base.md (items 9 to 11), from the exploratory
training run with the join-the-touch base (configs/runs/diag_train_touch.yaml).

  uv run python scripts/touch_base.py results/<diag_train_touch>

Exploratory: the overlays are ranked on training days, which is not the pre-registered
procedure (section 4 tunes overlays on validation days). Prints markdown.
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.eval import analysis
from toxic_flow.eval.bootstrap import mde

PRIMARY = ("risk_averse", "high")
N_TEST = 16
TARGET_MDE_BP = 0.1
Z = 2.80  # z_0.975 + z_0.80, section 9


def f(x, nd=3) -> str:
    return "none" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def grid_table(m: pl.DataFrame, label: str) -> pl.DataFrame:
    r = m.filter(pl.col("label") == label)
    return (
        r.group_by("params")
        .agg(mean_bef=pl.col("break_even_fee_bps").mean(),
             pooled=1e4 * pl.col("gross_pnl").sum() / pl.col("traded_notional").sum(),
             median_fills=pl.col("fills").median(), zero_days=(pl.col("fills") == 0).sum())
        .sort("mean_bef", descending=True)
    )  # fmt: skip


def cd(params: str) -> dict:
    p = json.loads(params)
    return {k: p[k] for k in ("c", "d", "tau_s") if k in p}


def daily(m: pl.DataFrame, label: str, params: str) -> dict:
    r = m.filter((pl.col("label") == label) & (pl.col("params") == params))
    return dict(zip(r["day"], r["break_even_fee_bps"], strict=True))


def power(m, b3: str, b2b: str) -> list[str]:
    a, b = daily(m, "B3_touch", b3), daily(m, "B2b_touch", b2b)
    d = np.array([a[k] - b[k] for k in sorted(a)])
    s = float(np.std(d, ddof=1))
    need = int(np.ceil((Z * s / TARGET_MDE_BP) ** 2)) if s > 0 else 0
    return [f"| {json.dumps(cd(b3))} | {json.dumps(cd(b2b))} | {len(d)} | {f(float(d.mean()))} | "
            f"{f(s)} | {f(mde(s, N_TEST))} | {need} |"]  # fmt: skip


def main(run: Path) -> None:
    meta = json.loads((run / "meta.json").read_text())
    if meta["config"] != "configs/runs/diag_train_touch.yaml":
        raise SystemExit(f"{run} is not diag_train_touch")
    m = pl.read_parquet(run / "metrics.parquet")
    L = [f"Run {meta['config_hash']} (configs/runs/diag_train_touch.yaml, commit {meta['commit'][:7]}),",
         f"{m['day'].n_unique()} training days. Exploratory throughout.", ""]  # fmt: skip

    L += ["## 9. The touch base T0 in all 8 cells", "",
          "Mean over days. Markouts per fill in our favour, averaged per day.", "",
          "| Queue model | Latency | Fills a day | BEF bp | Markout 1 s bp | Markout 10 s bp | Markout 60 s bp | Both sides resting | Bid at best |",
          "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    t0 = m.filter(pl.col("label") == "T0")
    for (q, lat), g in t0.group_by(["queue", "latency"], maintain_order=True):
        L.append(f"| {q} | {lat} | {f(float(g['fills'].mean()), 0)} | {f(float(g['break_even_fee_bps'].mean()))} | "
                 f"{f(float(g['mean_markout_1s_bps'].mean()))} | {f(float(g['mean_markout_10s_bps'].mean()))} | "
                 f"{f(float(g['mean_markout_60s_bps'].mean()))} | {f(float(g['quote_presence'].mean()))} | "
                 f"{f(float(g['bid_at_best_share'].mean()))} |")  # fmt: skip
    prim = m.filter(pl.col("queue").eq(PRIMARY[0]) & pl.col("latency").eq(PRIMARY[1]))
    L += ["", "Against B1 (selected) and B1 at gamma 0.2 in the primary cell:", "",
          "| Strategy | Fills a day | BEF bp |", "|---|---|---|"]  # fmt: skip
    for lab in ("T0", "B1", "B1_g0.2", "C2_touch"):
        g = prim.filter(pl.col("label") == lab)
        L.append(
            f"| {lab} | {f(float(g['fills'].mean()), 0)} | {f(float(g['break_even_fee_bps'].mean()))} |"
        )

    L += [
        "",
        "## 10. Overlays and C2 on the touch base (primary cell, exploratory tuning on training days)",
        "",
    ]
    for lab in ("B3_touch", "B2b_touch"):
        t = grid_table(m, lab)
        L += [f"### {lab}", "", "| Candidate | Mean daily BEF bp | Pooled BEF bp | Median fills | Days without fills |",
              "|---|---|---|---|---|"]  # fmt: skip
        L += [f"| {json.dumps(cd(r['params']))} | {f(r['mean_bef'])} | {f(r['pooled'])} | "
              f"{f(r['median_fills'], 0)} | {r['zero_days']} |" for r in t.iter_rows(named=True)]  # fmt: skip
        L.append("")
    L += ["The B2 (OFI) grid on this base (configs/runs/diag_train_touch_b2.yaml) was not run for",
          "time; B2 enters neither H1 nor the power projection.", "",
          "| Comparison | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |",
          "|---|---|---|---|---|---|"]  # fmt: skip
    for a, b in (("C2_touch", "T0"), ("T0", "B1")):
        c = analysis.compare(m, a, b)
        L.append(f"| {a} - {b} | {c['n']} | {f(c['mean'])} | [{f(c['bootstrap_ci'][0])}, {f(c['bootstrap_ci'][1])}] | "
                 f"[{f(c['t_ci'][0])}, {f(c['t_ci'][1])}] | {c['n_positive']} |")  # fmt: skip

    b3, b2b = grid_table(m, "B3_touch"), grid_table(m, "B2b_touch")
    nz = pl.col("params").map_elements(
        lambda p: cd(p)["c"] + cd(p)["d"] > 0, return_dtype=pl.Boolean
    )
    L += ["", "## 11. Power projection on this base (training days)", "",
          f"s is the standard deviation of the daily D_i = BEF_B3 - BEF_B2b; MDE = 2.80 s / sqrt({N_TEST});",
          f"days needed for an MDE of {TARGET_MDE_BP} bp = (2.80 s / {TARGET_MDE_BP})^2. Pairs: the best mean",
          "BEF of each (as section 4 would pick, but on training days), and the best with c or d above 0.", "",
          "| B3 setting | B2b setting | Days | Mean D bp | s bp | MDE on 16 days bp | Days for MDE 0.1 bp |",
          "|---|---|---|---|---|---|---|",
          *power(m, b3["params"][0], b2b["params"][0]),
          *power(m, b3.filter(nz)["params"][0], b2b.filter(nz)["params"][0])]  # fmt: skip
    print("\n".join(L))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
