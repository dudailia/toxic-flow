#!/usr/bin/env python3
"""Figures and the one-page PDF summary, from results/summary.json only (SPEC.md AC6.2).

Usage: uv run python paper/figures.py   (make paper runs it after the build)

- fig_daily_d.svg: D_i = BEF_B3 - BEF_B2b per test day in the primary cell, with the mean
  and both intervals (the per-day plot section 8 asks for).
- fig_cells.svg: the mean of D in each of the 8 queue and latency cells; H1 needs one sign.
- summary.pdf: one page that reprints chosen paragraphs of the built page (paper.md) and
  both plots. With --draft, summary_draft.pdf from draft.md: the same layout before the
  test days, with the test-day {{key}} placeholders open and empty figure frames.
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
    labels = [c.replace("risk_averse", "risk-\naverse").replace("/", "\n") for c in means]
    ax.set_xticks(range(len(means)), labels, fontsize=5.5)
    ax.set_ylabel("mean D, bp")
    ax.set_title("Mean D in every queue and latency cell", fontsize=9)


# The one-page PDF reprints these paragraphs of the built page, so it has the same text
# and, before the test, the same open {{key}} placeholders: (section heading, paragraphs).
# "" is the lead above the first section; None takes every paragraph.
PAGE = [
    ("", None),
    ("What the study asks", [0]),
    ("How the design changed before the test", None),
    ("Tuning and canaries on the validation days", [0]),
    ("Results on the test days", [0, 1]),
    ("Canaries on the test days", None),
]
FOOTER = (
    "Simulation on historical data only: no order was sent to an exchange, and nothing here "
    "is a claim about live trading or profit. Plan frozen by the git tag prereg-v1; full page "
    "and code at github.com/dudailia/toxic-flow."
)


def sections(md: str) -> tuple[str, dict]:
    """(title, {heading: [paragraphs]}) of a built page; tables, figures and code skipped."""
    title, heads, cur = "", {"": []}, ""
    for block in md.split("\n\n"):
        b = block.strip()
        if b.startswith("# "):
            title = b[2:]
        elif b.startswith("## "):
            cur = b[3:].strip()
            heads[cur] = []
        elif b and not b.startswith(("|", "![", "    ")):
            heads[cur].append(" ".join(b.split()))
    return title, heads


def page_text(md: str) -> tuple[str, list[str]]:
    title, heads = sections(md)
    out = []
    for head, picks in PAGE:
        paras = heads.get(head, [])
        chosen = paras if picks is None else [paras[i] for i in picks if i < len(paras)]
        if head:
            out.append(head.upper())
        out += chosen
    return title, out


def placeholder(ax, label: str) -> None:
    """A framed empty figure area for the draft, before the test days exist."""
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.5, 0.5, label, ha="center", va="center", fontsize=8, color="0.4", wrap=True)


def one_page(md: str, out: Path, s: dict | None) -> Path:
    """A4, one page: the chosen paragraphs of the built page, then the two figures (or,
    in the draft, empty frames that say what will be drawn there)."""
    title, paras = page_text(md)
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.06, 0.975, textwrap.fill(title, 70, break_on_hyphens=False), va="top", fontsize=12, weight="bold",
             family="serif")  # fmt: skip
    body = "\n\n".join(
        p if p.isupper() else textwrap.fill(p, 124) for p in paras
    )  # headings stay on their own line
    fig.text(0.06, 0.935, body, va="top", fontsize=6.5, family="serif", linespacing=1.2)
    a1, a2 = fig.add_axes((0.08, 0.11, 0.4, 0.15)), fig.add_axes((0.57, 0.11, 0.38, 0.15))
    if s is None:
        placeholder(a1, "Fig. 1, B3 minus B2b on each test day,\ndrawn from results/summary.json")
        placeholder(
            a2, "Fig. 2, mean B3 minus B2b in each of the\n8 cells, from results/summary.json"
        )
    else:
        daily_d(a1, s)
        cells(a2, s)
    fig.text(0.06, 0.015, textwrap.fill(FOOTER, 130), va="bottom", fontsize=6.5, color="0.3",
             family="serif")  # fmt: skip
    with PdfPages(out, metadata={"Title": title}) as pdf:
        pdf.savefig(fig)
    plt.close(fig)
    return out


def build_figures(s: dict, out: Path, md: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, draw in (("fig_daily_d.svg", daily_d), ("fig_cells.svg", cells)):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        draw(ax, s)
        fig.tight_layout()
        fig.savefig(out / name)
        plt.close(fig)
        paths.append(out / name)
    return [*paths, one_page(md, out / "summary.pdf", s)]


def main() -> int:
    if "--draft" in sys.argv[1:]:
        # Before the test: the one-page layout from the draft page, placeholders open.
        print(one_page((OUT / "draft.md").read_text(), OUT / "summary_draft.pdf", None))
        return 0
    summary = ROOT / "results" / "summary.json"
    if not summary.exists():
        print("no results/summary.json yet: it is written once the confirmatory runs exist")
        return 1
    md = (OUT / "paper.md").read_text()
    for p in build_figures(json.loads(summary.read_text()), OUT, md):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
