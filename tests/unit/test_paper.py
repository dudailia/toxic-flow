"""Paper scaffold: placeholders filled from results/summary.json, and the AC6.1 check."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "paper"))

from build_paper import build  # noqa: E402
from check_paper import check  # noqa: E402

TEMPLATE = """# Title

## Data

We use {{n_days}} days.

## Results

The mean difference is {{h1_mean_bp}} bp.

## Limitations

Fees were 0.02 percent in this example, outside a result section.
"""


def write(tmp_path, template=TEMPLATE, summary=None):
    (tmp_path / "template.md").write_text(template)
    (tmp_path / "summary.json").write_text(
        json.dumps(summary or {"n_days": 16, "h1_mean_bp": 0.123})
    )
    return tmp_path / "template.md", tmp_path / "summary.json"


def test_build_fills_every_placeholder(tmp_path):
    t, s = write(tmp_path)
    out = build(t, s, tmp_path / "paper.md")
    text = out.read_text()
    assert "{{" not in text and "16 days" in text and "0.1230 bp" in text


def test_build_fails_on_a_key_missing_from_the_summary(tmp_path):
    t, s = write(tmp_path, summary={"n_days": 16})
    with pytest.raises(KeyError):
        build(t, s, tmp_path / "paper.md")


def test_check_passes_a_clean_paper(tmp_path):
    t, s = write(tmp_path)
    assert check(t, build(t, s, tmp_path / "paper.md")) == []


def test_check_fails_on_an_unresolved_placeholder(tmp_path):
    t, _ = write(tmp_path)
    built = tmp_path / "paper.md"
    built.write_text("## Results\n\nThe value is {{h1_mean_bp}}.\n")
    assert any("unresolved" in p for p in check(t, built))


def test_check_fails_on_a_literal_decimal_in_a_result_section(tmp_path):
    t, s = write(tmp_path, template=TEMPLATE.replace("{{h1_mean_bp}}", "0.123"))
    problems = check(t, build(t, s, tmp_path / "paper.md"))
    assert any("literal decimal" in p and "0.123" in p for p in problems)


def test_the_real_template_passes_the_check(tmp_path):
    from build_paper import PLACEHOLDER

    template = Path(__file__).resolve().parents[2] / "paper" / "template.md"
    keys = set(PLACEHOLDER.findall(template.read_text()))
    (tmp_path / "summary.json").write_text(json.dumps({k: 1.0 for k in keys}))
    built = build(template, tmp_path / "summary.json", tmp_path / "paper.md")
    assert check(template, built) == []


def _summary():
    """A summary built by eval/analysis.py from a synthetic results table."""
    import numpy as np
    import polars as pl

    from toxic_flow.eval import analysis

    days = [f"2025-{m:02d}-01" for m in range(1, 13)]
    d = np.random.default_rng(0).normal(0.5, 0.3, len(days))
    rows = [
        {"day": day, "label": lab, "strategy": lab, "params": "{}", "queue": q, "latency": lat,
         "fills": 100, "traded_notional": 1e6, "break_even_fee_bps": v,
         "mean_markout_1s_bps": v, "mean_markout_10s_bps": v, "mean_markout_60s_bps": v}
        for q in ("risk_averse", "power3", "power2", "log") for lat in ("low", "high")
        for lab, vals in (("B1", [0.0] * 12), ("B2", [0.0] * 12), ("B2b", [0.0] * 12), ("B3", d))
        for day, v in zip(days, vals, strict=True)
    ]  # fmt: skip
    meta = {"hftbacktest": "2.4.4", "prereg_tagged_at": "t", "n_train_days": 12, "n_val_days": 6}
    return analysis.summary(pl.DataFrame(rows), {"s_bp": 0.3}, meta)


def test_figures_and_the_one_page_pdf_come_from_the_summary(tmp_path):
    # AC6.2 and the per-day plot of D_i in section 8, from summary.json only.
    from figures import build_figures

    paths = build_figures(_summary(), tmp_path)
    assert {p.name for p in paths} == {"fig_daily_d.svg", "fig_cells.svg", "summary.pdf"}
    pdf = (tmp_path / "summary.pdf").read_bytes()
    import re

    assert pdf.startswith(b"%PDF") and len(re.findall(rb"/Type\s*/Page(?!s)", pdf)) == 1
