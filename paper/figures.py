#!/usr/bin/env python3
"""Figures and the one-page PDF summary, from results/summary.json only (SPEC.md AC6.2).

Usage: uv run python paper/figures.py   (make paper runs it after the build)

- fig_daily_d.svg: D_i = BEF_B3 - BEF_B2b per test day in the primary cell, with the mean
  and both intervals (the per-day plot section 8 asks for).
- fig_cells.svg: the mean of D in each of the 8 queue and latency cells; H1 needs one sign.
- summary.pdf: one page with the H1 and canary statements, the numbers and both plots.
"""

import json
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # files only, no display
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "build"


def daily_d(ax, s: dict) -> None:
    p = s["h1"]["primary"]
    days, d = list(p["per_day"]), list(p["per_day"].values())
    ax.axhline(0, color="0.6", lw=0.8)
    ax.plot(range(len(d)), d, "o", color="C0", label="D on one test day")
    lo, hi = p["bootstrap_ci"]
    ax.axhspan(lo, hi, color="C1", alpha=0.15, label="95% bootstrap interval")
    for k, y in enumerate(p["t_ci"]):
        ax.axhline(y, color="C1", ls="--", lw=0.8, label="95% t interval" if k == 0 else None)
    ax.axhline(p["mean"], color="C1", lw=1.5, label="mean")
    ax.set_xticks(range(len(days)), [x[:7] for x in days], rotation=60, fontsize=7)
    ax.set_ylabel("BEF B3 minus B2b, bp")
    ax.set_title("Primary cell, per test day", fontsize=9)
    ax.legend(fontsize=6, loc="best")


def cells(ax, s: dict) -> None:
    means = s["h1"]["cell_means"]
    ax.axhline(0, color="0.6", lw=0.8)
    ax.bar(range(len(means)), list(means.values()), color="C0")
    ax.set_xticks(range(len(means)), [c.replace("/", "\n") for c in means], fontsize=6)
    ax.set_ylabel("mean D, bp")
    ax.set_title("Mean D in every queue and latency cell", fontsize=9)


def build_figures(s: dict, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, draw in (("fig_daily_d.svg", daily_d), ("fig_cells.svg", cells)):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        draw(ax, s)
        fig.tight_layout()
        fig.savefig(out / name)
        plt.close(fig)
        paths.append(out / name)
    with PdfPages(out / "summary.pdf", metadata={"Title": "toxic-flow summary"}) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4, one page
        text = "\n\n".join(
            textwrap.fill(t, 95)
            for t in (
                "Does a Hawkes estimate of order flow help a passive market maker? "
                "Simulation on historical BTCUSDT data only; no live trading, no real fills.",
                f"H1 (primary cell, {s['n_test_days']} test days): mean D = {s['h1_mean_bp']:.2f} bp, "
                f"bootstrap interval [{s['h1_ci_low_bp']:.2f}, {s['h1_ci_high_bp']:.2f}], "
                f"t interval [{s['h1_t_low_bp']:.2f}, {s['h1_t_high_bp']:.2f}], "
                f"MDE {s['mde_bp']:.2f} bp.",
                s["h1_statement"],
                "Canaries: " + (s["canary_statement"] or "none in these results."),
                f"Pre-registration tag prereg-v1 created {s['prereg_tagged_at']}; "
                f"hftbacktest {s['hftbacktest_version']}.",
            )
        )  # fmt: skip
        fig.text(0.07, 0.96, text, va="top", fontsize=8.5, family="serif")
        daily_d(fig.add_axes((0.1, 0.36, 0.85, 0.24)), s)
        cells(fig.add_axes((0.1, 0.06, 0.85, 0.2)), s)
        pdf.savefig(fig)
        plt.close(fig)
    return [*paths, out / "summary.pdf"]


def main() -> int:
    summary = ROOT / "results" / "summary.json"
    if not summary.exists():
        print("no results/summary.json yet: it is written once the confirmatory runs exist")
        return 1
    for p in build_figures(json.loads(summary.read_text()), OUT):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
