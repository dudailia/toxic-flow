"""Parameter selection by the rule in PREREGISTRATION.md section 4."""

import json

import polars as pl
import pytest

from toxic_flow.eval.select import at_edge, candidate_table, eligible, select

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
    # Overlays have no fill floor, so a day without fills still stops the selection.
    m = frame(
        rows("B3", {"c": 0.0, "d": 0.0}, [-0.5, -0.5]),
        rows("B3", {"c": 1.0, "d": 1.0}, [float("nan")] * 2, fills=0),
    )
    t = candidate_table(m, "B3", DAYS)
    assert t.filter(pl.col("zero_fill_days") > 0).height == 1
    with pytest.raises(ValueError, match="without fills"):
        select(t, "B3")


def test_b1_candidates_under_100_median_fills_are_not_eligible():
    # Section 4 grid-edge rule (Q41): the better BEF on 99 fills a day does not count, and
    # neither does a day without fills on an ineligible candidate.
    m = frame(
        rows("B1", {"gamma": 0.2}, [-0.7, -0.7], fills=100),
        rows("B1", {"gamma": 0.4}, [-0.1, -0.1], fills=99),
        rows("B1", {"gamma": 0.8}, [float("nan")] * 2, fills=0),
    )
    t = candidate_table(m, "B1", DAYS)
    assert eligible(t).to_list() == [True, False, False]  # sorted by params: 0.2, 0.4, 0.8
    out = select(t, "B1")
    assert out["params"]["gamma"] == 0.2 and out["mean_bef_bps"] == pytest.approx(-0.7)


def test_no_eligible_candidate_is_left_to_ilia():
    m = frame(rows("B0", {"h": 13}, [-0.5, -0.5], fills=10))
    with pytest.raises(ValueError, match="median daily fills"):
        select(candidate_table(m, "B0", DAYS), "B0")


def test_edges_of_a_grid():
    assert at_edge(5, (1, 2, 3, 5)) == "high" and at_edge(1, (1, 2, 3, 5)) == "low"
    assert at_edge(0.2, (0.025, 0.05, 0.1, 0.2, 0.4, 0.8)) is None


def test_a_candidate_missing_a_day_is_refused():
    m = frame(rows("B1", {"gamma": 0.05}, [-0.5, -0.5]))
    with pytest.raises(ValueError, match="missing"):
        candidate_table(m, "B1", [*DAYS, "2025-03-01"])


def test_an_eligible_b1_candidate_with_a_day_without_fills_is_left_to_ilia():
    # Median of (0, 200) is 100, so it is eligible; its BEF on the empty day is undefined.
    m = pl.DataFrame(
        rows("B1", {"gamma": 0.2}, [-0.7, -0.7])
        + [r | {"fills": f} for r, f in zip(rows("B1", {"gamma": 0.4}, [float("nan"), -0.1]),
                                            (0, 200), strict=True)]
    )  # fmt: skip
    t = candidate_table(m, "B1", DAYS)
    assert eligible(t).all()
    with pytest.raises(ValueError, match="without fills"):
        select(t, "B1")
