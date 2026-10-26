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
    keys = {k for k in PLACEHOLDER.findall(template.read_text()) if not k.startswith("pre_")}
    (tmp_path / "summary.json").write_text(json.dumps({k: 1.0 for k in keys}))
    built = build(template, tmp_path / "summary.json", tmp_path / "paper.md", PRE_TEST)
    assert check(template, built) == []


PRE_TEST = Path(__file__).resolve().parents[2] / "paper" / "pre_test.json"


def test_a_pre_test_key_in_the_summary_is_refused(tmp_path):
    t, _ = write(tmp_path, template="## Results\n\n{{h1_mean_bp}}\n")
    (tmp_path / "s.json").write_text(json.dumps({"h1_mean_bp": 0.1, "pre_mde": "0.02"}))
    with pytest.raises(KeyError, match="pre-test keys"):
        build(t, tmp_path / "s.json", tmp_path / "paper.md", PRE_TEST)


def test_the_draft_fills_pre_test_keys_and_leaves_every_test_key_open(tmp_path):
    from build_paper import PLACEHOLDER

    template = Path(__file__).resolve().parents[2] / "paper" / "template.md"
    built = build(template, None, tmp_path / "draft.md", PRE_TEST, draft=True)
    left = set(PLACEHOLDER.findall(built.read_text()))
    wanted = {k for k in PLACEHOLDER.findall(template.read_text()) if not k.startswith("pre_")}
    assert left == wanted and "h1_mean_bp" in left
    assert check(template, built, draft=True) == []


def test_the_committed_pre_test_numbers_are_what_the_script_computes_now():
    from pre_test import build as pre_build

    assert json.loads(PRE_TEST.read_text()) == pre_build()


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
        for lab, vals in (("B1", [0.0] * 12), ("B2", [0.0] * 12), ("B2b", [0.0] * 12), ("B3", d),
                          ("C1", [0.0] * 12), ("C2", [2.0] * 12),
                          *((f"{r}_s{k}", list(d * k / 10)) for r in ("R1", "R_B3", "R_B2b", "RL_B3", "RL_B2b")
                            for k in (1, 2, 3)))
        for day, v in zip(days, vals, strict=True)
    ]  # fmt: skip
    meta = {"hftbacktest": "2.4.4", "prereg_tagged_at": "t", "n_train_days": 12, "n_val_days": 6}
    return analysis.summary(pl.DataFrame(rows), {"s_bp": 0.3}, meta)


def test_figures_and_the_one_page_pdf_come_from_the_summary(tmp_path):
    # AC6.2 and the per-day plot of D_i in section 8, from summary.json only.
    from figures import build_figures

    s = _summary()
    template = Path(__file__).resolve().parents[2] / "paper" / "template.md"
    (tmp_path / "s.json").write_text(json.dumps({k: v for k, v in s.items()
                                                 if not isinstance(v, dict)}))  # fmt: skip
    page = build(template, tmp_path / "s.json", tmp_path / "paper.md", PRE_TEST).read_text()
    paths = build_figures(s, tmp_path, page)
    assert {p.name for p in paths} == {"fig_daily_d.svg", "fig_cells.svg", "summary.pdf"}
    assert one_page_count(tmp_path / "summary.pdf") == 1


def one_page_count(path: Path) -> int:
    import re

    pdf = path.read_bytes()
    assert pdf.startswith(b"%PDF")
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf))


def test_the_draft_pdf_is_one_page_with_the_same_paragraphs_as_the_page(tmp_path):
    from figures import one_page, page_text

    template = Path(__file__).resolve().parents[2] / "paper" / "template.md"
    draft = build(template, None, tmp_path / "draft.md", PRE_TEST, draft=True).read_text()
    _, paras = page_text(draft)
    assert "{{h1_statement}}" in paras and "{{canary_statement}}" in paras
    assert all(p in " ".join(draft.split()) for p in paras if not p.isupper())
    assert one_page_count(one_page(draft, tmp_path / "d.pdf", None)) == 1


def test_a_missing_page_section_stops_the_pdf_instead_of_dropping_it():
    from figures import page_text

    with pytest.raises(KeyError, match="no section"):
        page_text("# Title\n\nLead.\n\n## What the study asks\n\nQ.\n")
