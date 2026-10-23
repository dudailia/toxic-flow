"""Sections 7, 8, 9 and 10 on synthetic results tables (eval/analysis.py)."""

import re
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from toxic_flow.eval import analysis
from toxic_flow.eval.bootstrap import bootstrap_ci

DAYS = [f"2025-{m:02d}-01" for m in range(1, 13)]
QUEUES = ["risk_averse", "power3", "power2", "log"]


def rows(label, bef, queue="risk_averse", latency="high", fills=100, notional=1e6, params=None):
    """One row per day; bef is a list of daily BEF values."""
    return [
        {"day": d, "label": label, "strategy": label.split("_")[0], "queue": queue,
         "latency": latency, "params": params or f'{{"name": "{label}"}}', "fills": fills,
         "break_even_fee_bps": b, "traded_notional": notional,
         "mean_markout_1s_bps": b, "mean_markout_10s_bps": b / 2, "mean_markout_60s_bps": b / 4}
        for d, b in zip(DAYS, bef, strict=True)
    ]  # fmt: skip


def grid(label, bef, **kw):
    """The same daily values in all 8 queue and latency cells."""
    return [r for q in QUEUES for lat in ("low", "high") for r in rows(label, bef, q, lat, **kw)]


NOISE = np.random.default_rng(0).normal(0, 0.1, len(DAYS))


def test_compare_is_a_minus_b_per_day_with_the_preregistered_intervals():
    m = pl.DataFrame(rows("B3", list(1.0 + NOISE)) + rows("B2b", [0.0] * 12))
    out = analysis.compare(m, "B3", "B2b")
    d = 1.0 + NOISE
    assert out["n"] == 12 and out["dropped"] == []
    assert out["mean"] == pytest.approx(d.mean())
    assert out["bootstrap_ci"] == pytest.approx(bootstrap_ci(d))
    assert out["n_positive"] == 12
    assert out["per_day"] == pytest.approx(dict(zip(DAYS, d, strict=True)))


def test_a_day_where_either_side_has_no_fills_is_dropped_and_listed():
    b3 = rows("B3", list(1.0 + NOISE))
    b3[0]["fills"] = 0
    out = analysis.compare(pl.DataFrame(b3 + rows("B2b", [0.0] * 12)), "B3", "B2b")
    assert out["n"] == 11 and out["dropped"] == [DAYS[0]]


def test_two_parameter_sets_for_one_label_in_a_cell_are_refused():
    m = pl.DataFrame(rows("B3", [1.0] * 12) + rows("B3", [2.0] * 12, params='{"c": 1}'))
    with pytest.raises(ValueError, match="parameter sets"):
        analysis.compare(m, "B3", "B2b")


def test_h1_holds_only_with_the_same_sign_in_all_8_cells():
    base = grid("B2b", [0.0] * 12)
    holds = analysis.h1(pl.DataFrame(base + grid("B3", list(1.0 + NOISE))), mde_bp=0.5)
    assert holds["key"] == "holds_positive"
    assert len(holds["cell_means"]) == 8
    flipped = [
        {**r, "break_even_fee_bps": -r["break_even_fee_bps"]}
        if (r["queue"], r["latency"]) == ("log", "low") else r
        for r in grid("B3", list(1.0 + NOISE))
    ]  # fmt: skip
    assert analysis.h1(pl.DataFrame(base + flipped), mde_bp=0.5)["key"] == "does_not_hold"


def test_selectivity_flags_b3_trading_less_than_half_of_b2b():
    m = pl.DataFrame(
        grid("B2b", [0.0] * 12) + grid("B3", list(1.0 + NOISE), notional=4e5)
    )  # fmt: skip
    assert analysis.h1(m, mde_bp=0.5)["selectivity"]["flag"]


def test_exploratory_pairs_and_markout_differences():
    m = pl.DataFrame(
        rows("B1", [0.0] * 12) + rows("B2", [0.5] * 12)
        + rows("B2b", list(0.2 + NOISE)) + rows("B3", list(1.0 + NOISE))
    )  # fmt: skip
    out = analysis.exploratory(m)
    assert set(out) == {"H2", "H3", "H4"}
    assert out["H3"]["bef"]["mean"] == pytest.approx((1.0 + NOISE).mean())
    assert out["H3"]["markout_10s"]["mean"] == pytest.approx((1.0 + NOISE).mean() / 2)
    assert out["H2"]["label"] == "exploratory"


def test_canaries_by_section_10():
    m = pl.DataFrame(
        rows("B1", [0.0] * 12) + rows("B3", [0.3] * 12)
        + rows("C1", list(NOISE))  # signs shuffled: no gain over B1
        + rows("C2", [5.0] * 12)  # the oracle wins by far
        + rows("B3", [0.2] * 12, latency="zero")  # C3 below B3 at high latency
        + rows("C4_x10", list(0.3 + NOISE)) + rows("C4_x0.1", [-1.0] * 12)
    )  # fmt: skip
    out = analysis.canaries(m, mde_bp=1.0)
    assert out["C1"]["pass"] and out["C2"]["pass"]
    assert out["C3"]["flag"]  # B3 at high latency beats its zero-latency run
    assert out["C4"]["decay_not_driver"]  # x10 matches B3 within the interval
    assert "fitted decay is not what drives" in out["statement"]


def test_c1_fails_when_shuffled_signs_still_beat_b1():
    m = pl.DataFrame(rows("B1", [0.0] * 12) + rows("C1", list(1.0 + NOISE)))
    out = analysis.canaries(m, mde_bp=1.0)
    assert not out["C1"]["pass"]
    assert "not order-flow information" in out["statement"]


def test_s_is_the_larger_of_the_training_and_validation_estimates():
    train = pl.DataFrame(rows("B3", list(NOISE)) + rows("B2b", [0.0] * 12))
    val = pl.DataFrame(rows("B3", list(3 * NOISE)) + rows("B2b", [0.0] * 12))
    out = analysis.mde_inputs(train, val, n_test=16)
    assert out["s_bp"] == pytest.approx(np.std(3 * NOISE, ddof=1))
    assert out["mde_bp"] == pytest.approx(analysis.mde(out["s_bp"], 16))


def test_summary_has_every_key_the_paper_template_needs():
    template = (Path(__file__).resolve().parents[2] / "paper" / "template.md").read_text()
    needed = set(re.findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", template))
    m = pl.DataFrame(
        grid("B1", [0.0] * 12) + grid("B2", [0.5] * 12) + grid("B2b", [0.0] * 12)
        + grid("B3", list(1.0 + NOISE)) + rows("C1", list(NOISE)) + rows("C2", [5.0] * 12)
        + rows("B3", [0.2] * 12, latency="zero") + rows("C4_x10", [0.0] * 12)
        + rows("C4_x0.1", [0.0] * 12)
    )  # fmt: skip
    mde = {"s_bp": 1.0, "mde_bp": 0.7, "n_test": 16}
    meta = {"hftbacktest": "2.4.4", "prereg_pushed_at": "2026-11-01T00:00:00+00:00",
            "n_train_days": 12, "n_val_days": 6}  # fmt: skip
    summary = analysis.summary(m, mde, meta)
    assert needed <= set(summary)
    assert summary["n_test_days"] == 12


def test_only_a_full_non_smoke_test_run_may_write_the_paper_summary():
    test_days = ["2025-07-01", "2025-08-01"]
    ok = analysis.confirmatory_problem([{"label": "confirmatory"}], test_days, test_days)
    assert ok is None
    assert "smoke" in analysis.confirmatory_problem([{"label": "smoke"}], test_days, test_days)
    assert "test days" in analysis.confirmatory_problem(
        [{"label": "confirmatory"}], test_days[:1], test_days
    )


def test_a_repeated_day_is_kept_once_if_identical_and_refused_if_not():
    same = pl.DataFrame(rows("B3", [1.0] * 12) * 2 + rows("B2b", [0.0] * 12))
    assert analysis.compare(same, "B3", "B2b")["n"] == 12
    differs = rows("B3", [1.0] * 12) + rows("B3", [2.0] * 12) + rows("B2b", [0.0] * 12)
    with pytest.raises(ValueError, match="twice"):
        analysis.compare(pl.DataFrame(differs), "B3", "B2b")


def test_without_an_interval_there_is_no_conclusion():
    # One paired day gives no interval; NaN must not read as "excludes 0".
    one = pl.DataFrame(rows("B3", [1.0] * 12) + rows("B2b", [0.0] * 12)).filter(
        pl.col("day") == DAYS[0]
    )
    nan = (float("nan"), float("nan"))
    from toxic_flow.eval.bootstrap import conclusion

    assert conclusion(nan, nan, 1.0, [1.0] * 8, 0.5)["key"] == "not_computed"
    m = pl.concat([one, pl.DataFrame(rows("B1", [0.0] * 12) + rows("C1", [1.0] * 12))
                  .filter(pl.col("day") == DAYS[0])], how="diagonal_relaxed")  # fmt: skip
    c = analysis.canaries(m, mde_bp=1.0)
    assert c["C1"]["pass"] is None
    assert "not order-flow information" not in c["statement"]
