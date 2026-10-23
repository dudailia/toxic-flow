"""Parameter selection by the rule in PREREGISTRATION.md section 4."""

import json

import polars as pl
import pytest

from toxic_flow.eval.select import candidate_table, select

DAYS = ["2025-01-01", "2025-02-01"]


def rows(strategy, params, befs, queue="risk_averse", latency="high", fills=100):
    p = json.dumps({"name": strategy, **params}, sort_keys=True)
    return [
        {"day": d, "strategy": strategy, "params": p, "queue": queue, "latency": latency,
         "fills": fills, "break_even_fee_bps": b}
        for d, b in zip(DAYS, befs, strict=True)
    ]  # fmt: skip


def frame(*groups):
    return pl.DataFrame([r for g in groups for r in g])


def test_the_highest_mean_daily_bef_in_the_primary_cell_wins():
    m = frame(
        rows("B2b", {"c": 0.5, "d": 0.0, "tau_s": 5.0}, [-1.0, -0.6]),
        rows("B2b", {"c": 1.0, "d": 0.5, "tau_s": 1.0}, [-0.5, -0.7]),
        # Better, but outside the primary cell, so it must not count.
        rows("B2b", {"c": 1.0, "d": 1.0, "tau_s": 1.0}, [5.0, 5.0], queue="log"),
    )
    t = candidate_table(m, "B2b", DAYS)
    assert len(t) == 2
    out = select(t, "B2b")
    assert out["params"]["c"] == 1.0 and out["params"]["d"] == 0.5
    assert out["mean_bef_bps"] == pytest.approx(-0.6)


def test_ties_go_to_the_smaller_c_plus_d_then_the_shorter_window():
    # c = d = 0 reduces every overlay to B1, so all windows tie exactly.
    m = frame(
        rows("B2", {"c": 0.0, "d": 0.0, "ofi_window_s": 30.0}, [-0.5, -0.5]),
        rows("B2", {"c": 0.0, "d": 0.0, "ofi_window_s": 1.0}, [-0.5, -0.5]),
        rows("B2", {"c": 0.0, "d": 0.0, "ofi_window_s": 5.0}, [-0.5, -0.5]),
        rows("B2", {"c": 0.5, "d": 0.5, "ofi_window_s": 1.0}, [-0.5, -0.5]),
    )
    out = select(candidate_table(m, "B2", DAYS), "B2")
    assert out["params"] == {"name": "B2", "c": 0.0, "d": 0.0, "ofi_window_s": 1.0}
    assert out["tied"] == 4


def test_a_tie_the_rule_cannot_break_is_left_to_ilia():
    m = frame(
        rows("B3", {"c": 1.0, "d": 0.0}, [-0.5, -0.5]),
        rows("B3", {"c": 0.0, "d": 1.0}, [-0.5, -0.5]),
    )
    with pytest.raises(ValueError, match="tie"):
        select(candidate_table(m, "B3", DAYS), "B3")


def test_section_4_has_no_tie_rule_for_b0_and_b1():
    m = frame(rows("B0", {"h": 1}, [-0.5, -0.5]), rows("B0", {"h": 2}, [-0.5, -0.5]))
    with pytest.raises(ValueError, match="no tie rule"):
        select(candidate_table(m, "B0", DAYS), "B0")


def test_a_day_without_fills_is_left_to_ilia():
    m = frame(
        rows("B1", {"gamma": 0.05}, [-0.5, -0.5]),
        rows("B1", {"gamma": 5.0}, [float("nan")] * 2, fills=0),
    )
    t = candidate_table(m, "B1", DAYS)
    assert t.filter(pl.col("zero_fill_days") > 0).height == 1
    with pytest.raises(ValueError, match="without fills"):
        select(t, "B1")


def test_a_candidate_missing_a_day_is_refused():
    m = frame(rows("B1", {"gamma": 0.05}, [-0.5, -0.5]))
    with pytest.raises(ValueError, match="missing"):
        candidate_table(m, "B1", [*DAYS, "2025-03-01"])
