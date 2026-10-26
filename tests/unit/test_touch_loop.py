"""The v2 loop on a synthetic day: the signal equals the offline causal functions, and every
step's quotes are the section 4 rule applied to that step's book, inventory and signal,
so the toxic side is the one that steps back inside the loop too. Slow: engine runs."""

import numpy as np
import pytest
from synthetic import T0, synthetic_day

from toxic_flow.data.book import replay_bbo
from toxic_flow.data.convert import convert_parts
from toxic_flow.events.market_orders import collapse
from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_online import hawkes_signal
from toxic_flow.signals.normalise import magnitude, trailing_mean
from toxic_flow.signals.ofi import ofi_contributions, ofi_window, trailing_std
from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE
from toxic_flow.strategies.signal_input import EWMA, HAWKES, NONE, OFI
from toxic_flow.strategies.touch import PULL, run_touch, touch_quote

N, K, TAU, W_NS = 10, 2.0, 0.5, 300_000_000
MU, ALPHA, BETA = np.array([3.0, 3.0]), np.array([[2.0, 1.0], [1.0, 2.0]]), 8.0
pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def day(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("day")
    trades, depth = synthetic_day(tmp)
    (data,), _ = convert_parts(trades, depth, n_parts=1)
    np.savez_compressed(tmp / "day.npz", data=data)
    events, _ = collapse(trades)
    ev_ts = events["local_ts"].to_numpy()
    ev_side = (events["side"] == "s").to_numpy().astype(np.int64)
    bbo, _ = replay_bbo([tmp / "day.npz"], 0.05, 0.001)
    ofi_ts, e = ofi_contributions(bbo)
    return tmp / "day.npz", ev_ts, ev_side, ofi_ts, np.concatenate([[0.0], np.cumsum(e)]), e


def run(day, mode, skew, theta_u, k_ticks, theta_m):
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest

    path, ev_ts, ev_side, ofi_ts, cum, _ = day
    asset = (
        BacktestAsset().data([str(path)]).linear_asset(1.0).constant_order_latency(1_000_000, 1_000_000)
        .risk_adverse_queue_model().no_partial_fill_exchange().trading_value_fee_model(0.0, 0.0)
        .tick_size(0.05).lot_size(0.001).last_trades_capacity(1000)
    )  # fmt: skip
    hbt = HashMapMarketDepthBacktest([asset])
    steps, fills, out, diag = (
        np.zeros(500, STEP_DTYPE), np.zeros(500, FILL_DTYPE), np.zeros(13), np.zeros((500, 3)),
    )  # fmt: skip
    sig_ts, sig_side = (
        (ofi_ts, np.zeros(len(ofi_ts), np.int64)) if mode == OFI else (ev_ts, ev_side)
    )
    t0 = T0 * 1000
    run_touch(
        hbt, 0.001, 100.0, 10, t0 + 2 * 10**9, t0 + 6 * 10**9, 100_000_000, steps, fills, out,
        skew, mode, K, N, sig_ts, sig_side, cum, TAU, W_NS, MU, ALPHA, BETA,
        np.zeros(0), np.zeros(0), theta_u, k_ticks, theta_m, diag,
    )  # fmt: skip
    hbt.close()
    n = int(np.count_nonzero(diag[:, 0]))
    return diag[:n], steps[: int(out[0])], out


@pytest.mark.parametrize("mode", [OFI, EWMA, HAWKES])
def test_loop_signal_equals_the_offline_causal_functions(day, mode):
    _, ev_ts, ev_side, ofi_ts, _, e = day
    diag, _, _ = run(day, mode, True, 0.3, 1, 0.2)
    ts = diag[:, 0].astype(np.int64)
    if mode == OFI:
        ofi = ofi_window(ofi_ts, e, ts, W_NS / 1e9)
        s = trailing_std(ofi, N)
        with np.errstate(divide="ignore", invalid="ignore"):
            u = np.where(s > 0, np.tanh(ofi / s), 0.0)
        a = np.abs(ofi)
    elif mode == EWMA:
        u, a = ewma_at(ev_ts, ev_side, ts, TAU)
    else:
        u, a = hawkes_signal(ev_ts, ev_side, ts, MU, ALPHA, BETA)
    np.testing.assert_allclose(diag[:, 1], u, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(diag[:, 2], magnitude(a, trailing_mean(a, N), K), atol=1e-9)


# Thresholds near the median |u| of each signal on this short synthetic day, so both
# toxic and quiet steps occur.
@pytest.mark.parametrize(
    ("mode", "theta_u", "k_ticks"), [(EWMA, 0.13, 1), (HAWKES, 0.04, 5), (OFI, 0.5, PULL)]
)
def test_every_step_quotes_the_section_4_rule(day, mode, theta_u, k_ticks):
    diag, steps, out = run(day, mode, True, theta_u, k_ticks, 0.2)
    at = {int(t): (u, m) for t, u, m in diag}
    assert len(steps) > 20
    toxic_steps = 0
    for s in steps:
        if not np.isfinite(s["mid"]):
            continue
        u, m = at[int(s["ts"])]
        q = round(s["position"] / out[5])
        bid, ask, qb, qa, toxic = touch_quote(
            int(s["best_bid_tick"]), int(s["best_ask_tick"]), q, True, u, m, theta_u, k_ticks, 0.2
        )
        assert s["toxic"] == toxic
        assert s["bid_tick"] == bid if qb and q < 10 else np.isnan(s["bid_tick"])
        assert s["ask_tick"] == ask if qa and q > -10 else np.isnan(s["ask_tick"])
        toxic_steps += toxic != 0
    assert 0 < toxic_steps < len(steps)  # both branches were exercised


def test_b0_quotes_the_touch_and_never_marks_a_side_toxic(day):
    _, steps, _ = run(day, NONE, False, np.inf, 1, np.inf)
    ok = np.isfinite(steps["mid"]) & np.isfinite(steps["bid_tick"])
    assert ok.sum() > 20
    assert np.array_equal(steps["bid_tick"][ok], steps["best_bid_tick"][ok])
    assert np.all(steps["toxic"] == 0)
