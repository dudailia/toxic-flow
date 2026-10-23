"""AC2.2 and AC2.3 on the benchmark day 2024-01-01 (slow: each run replays the full day)."""

from pathlib import Path

import pytest

from toxic_flow.engine.run import run_cell

DAY = "2024-01-01"
CONVERTED = Path(__file__).resolve().parents[2] / "data" / "converted" / DAY / "convert.json"
CFG = {
    "quote_start": "00:30:00",
    "quote_end": "23:59:00",
    "step_ns": 100_000_000,
    "max_lots": 10,
    "fee_levels_bps": {"standard_maker": "venue", "zero": 0.0},
}
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not CONVERTED.exists(), reason="2024-01-01 not converted"),
]


def cell(strategy, queue="risk_averse", latency="low"):
    return {"day": DAY, "strategy": strategy, "queue": queue, "latency": latency}


@pytest.mark.parametrize(
    "strategy", [{"name": "B0", "h": 1}, {"name": "B1", "gamma": 0.05, "window_s": 600}]
)
def test_ac2_2_pnl_from_fills_reconciles_with_engine_cash_and_inventory(strategy):
    row, fills = run_cell(cell(strategy), CFG)
    engine_gross = row["engine_cash"] + row["engine_position"] * row["mark_mid"]
    assert abs(row["gross_pnl"] - engine_gross) <= 1e-6
    assert row["fills"] == row["engine_fills"] == len(fills)
    assert row["end_position"] == pytest.approx(row["engine_position"], abs=1e-12)
    # Within a step hftbacktest returns orders in hash-map order, which changes between
    # processes; sorted fills make every sum, and so every metric, identical across runs.
    key = fills.select("local_ts", "order_id")
    assert key.equals(key.sort(["local_ts", "order_id"]))


def test_ac2_3_engine_maker_fee_equals_the_post_hoc_fee():
    b0 = {"name": "B0", "h": 1}
    free, _ = run_cell(cell(b0), CFG)
    paid, _ = run_cell(cell(b0), CFG, maker_fee_bps=2.0)
    assert paid["fills"] == free["fills"]  # fees do not change behaviour
    engine_net = (
        paid["engine_cash"] + paid["engine_position"] * paid["mark_mid"] - paid["engine_fee"]
    )
    assert abs(engine_net - free["net_pnl_standard_maker"]) <= 1e-6
    assert paid["engine_fee"] == pytest.approx(2.0 / 1e4 * paid["engine_traded_value"], rel=1e-12)
