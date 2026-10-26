"""Metrics and markouts (PREREGISTRATION.md section 6) on hand-made fills."""

import numpy as np
import pytest

from toxic_flow.eval.markouts import markouts
from toxic_flow.eval.metrics import day_metrics, window_metrics
from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE

S = 10**9


def fills(rows):
    out = np.zeros(len(rows), FILL_DTYPE)
    for i, (ts, side, px, qty) in enumerate(rows):
        out[i]["exch_ts"], out[i]["local_ts"] = ts, ts
        out[i]["side"], out[i]["price"], out[i]["qty"] = side, px, qty
    return out


def steps(n, mid=100.0, position=0.0, both=True):
    out = np.zeros(n, STEP_DTYPE)
    out["ts"] = np.arange(n, dtype=np.int64) * 100_000_000
    out["mid"] = mid
    out["position"] = position
    out["both_quoted"] = both
    return out


def test_gross_pnl_notional_break_even_fee_and_net():
    f = fills([(1 * S, 1, 100.0, 1.0), (2 * S, -1, 100.5, 1.0), (3 * S, 1, 100.2, 1.0)])
    st = steps(40)
    m = day_metrics(
        f, st, mark_mid=101.0, order_qty=1.0, fee_levels_bps={"maker": 2.0, "zero": 0.0}
    )
    gross = -100.0 + 100.5 - 100.2 + 1.0 * 101.0  # cash plus final inventory at the mark
    notional = 100.0 + 100.5 + 100.2
    assert m["gross_pnl"] == pytest.approx(gross)
    assert m["traded_notional"] == pytest.approx(notional)
    assert m["break_even_fee_bps"] == pytest.approx(1e4 * gross / notional)
    assert m["net_pnl"]["maker"] == pytest.approx(gross - 2.0 * notional / 1e4)
    assert m["net_pnl"]["zero"] == pytest.approx(gross)
    assert m["fills"] == 3 and m["end_position"] == pytest.approx(1.0)


def test_inventory_variance_fill_rate_presence_and_funding_inventory():
    st = steps(36_000)  # one hour of 100 ms steps
    st["position"][18_000:] = 2.0  # two order sizes from 30 minutes on
    st["both_quoted"][:9_000] = False
    m = day_metrics(fills([(1 * S, 1, 100.0, 2.0)]), st, 100.0, order_qty=1.0, fee_levels_bps={})
    q = st["position"][::10]  # sampled each second
    assert m["inventory_variance"] == pytest.approx(q.var())
    assert m["fill_rate_per_hour"] == pytest.approx(1.0)
    assert m["quote_presence"] == pytest.approx(0.75)


def test_inventory_at_funding_times_reads_the_first_step_at_or_after_each():
    from toxic_flow.eval.metrics import inventory_at

    st = steps(100)
    st["position"] = np.arange(100, dtype=float)
    assert inventory_at(st, [int(2.05 * S), int(50 * S)]) == [21.0, None]


def test_markouts_sign_and_horizons():
    st = steps(200)
    st["mid"][21:] = 101.0  # mid rises 1 USDT at 2.1 s
    f = fills([(1 * S, 1, 100.0, 1.0), (1 * S, -1, 100.0, 1.0), (19 * S, 1, 100.0, 1.0)])
    mk = markouts(f, st, horizons_s=(1, 10))
    assert mk["markout_1s_bps"][0] == pytest.approx(0.0)  # at 2 s the mid is still 100
    assert mk["markout_10s_bps"][0] == pytest.approx(100.0)  # bought at 100, mid 101: +100 bp
    assert mk["markout_10s_bps"][1] == pytest.approx(-100.0)  # sold at 100: adverse
    assert np.isnan(mk["markout_10s_bps"][2])  # 29 s is past the recorded steps


def test_window_metrics_mark_the_inventory_held_at_the_window_start():
    # Buy 1 at 100 before the window, sell 1 at 101 and buy 1 at 100.5 inside it; the mid
    # at the window start (step at 2 s) is 100.4, the end mark 101.
    f = fills([(1 * S, 1, 100.0, 1.0), (3 * S, -1, 101.0, 1.0), (4 * S, 1, 100.5, 1.0)])
    st = steps(60)
    st["mid"][20:] = 100.4
    w = window_metrics(f, st, mark_mid=101.0, from_ns=2 * S)
    assert w["fills"] == 2
    assert w["traded_notional"] == pytest.approx(101.0 + 100.5)
    gross = (101.0 - 100.5) + 1.0 * 101.0 - 1.0 * 100.4  # cash in window, end q, start q
    assert w["gross_pnl"] == pytest.approx(gross)
    assert w["break_even_fee_bps"] == pytest.approx(1e4 * gross / (101.0 + 100.5))
    # Window plus the part before it is the whole day.
    full = day_metrics(f, st, mark_mid=101.0, order_qty=1.0, fee_levels_bps={})
    before = -100.0 + 1.0 * 100.4
    assert full["gross_pnl"] == pytest.approx(w["gross_pnl"] + before)


def test_a_window_from_the_first_step_is_the_whole_day():
    f = fills([(1 * S, 1, 100.0, 1.0), (2 * S, -1, 100.5, 1.0)])
    st = steps(40)
    w = window_metrics(f, st, mark_mid=101.0, from_ns=0)
    full = day_metrics(f, st, mark_mid=101.0, order_qty=1.0, fee_levels_bps={})
    for k in ("fills", "gross_pnl", "traded_notional", "break_even_fee_bps"):
        assert w[k] == pytest.approx(full[k])


def test_toxic_episodes_count_runs_of_one_side():
    from toxic_flow.eval.metrics import toxic_episodes

    assert toxic_episodes(np.array([0, 1, 1, 0, -1, 1, 1, 0, 0, -1], np.int8)) == 4
    assert toxic_episodes(np.array([1, 1, 1], np.int8)) == 1
    assert toxic_episodes(np.zeros(5, np.int8)) == 0 and toxic_episodes(np.zeros(0)) == 0
