"""The overlay loop computes each signal exactly as the offline causal functions do, and
with c = d = 0 every overlay trades exactly like B1. Slow: engine runs on a synthetic day."""

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
from toxic_flow.strategies.overlay import EWMA, HAWKES, NONE, OFI, run_overlay

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


def run(day, mode, c, d):
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest

    path, ev_ts, ev_side, ofi_ts, cum, _ = day
    asset = (
        BacktestAsset().data([str(path)]).linear_asset(1.0).constant_order_latency(1_000_000, 1_000_000)
        .risk_adverse_queue_model().no_partial_fill_exchange().trading_value_fee_model(0.0, 0.0)
        .tick_size(0.05).lot_size(0.001).last_trades_capacity(1000)
    )  # fmt: skip
    hbt = HashMapMarketDepthBacktest([asset])
    steps, fills, out, diag = (
        np.zeros(500, STEP_DTYPE),
        np.zeros(500, FILL_DTYPE),
        np.zeros(13),
        np.zeros((500, 3)),
    )
    sig_ts, sig_side = (
        (ofi_ts, np.zeros(len(ofi_ts), np.int64)) if mode == OFI else (ev_ts, ev_side)
    )
    t0 = T0 * 1000
    run_overlay(
        hbt, 0.05, 20, 5, 0.001, 100.0, 10, t0 + 2 * 10**9, t0 + 6 * 10**9, 100_000_000,
        steps, fills, out, mode, c, d, K, N, sig_ts, sig_side, cum, TAU, W_NS, MU, ALPHA, BETA,
        np.zeros(0), np.zeros(0), diag,
    )  # fmt: skip
    hbt.close()
    n = int(np.count_nonzero(diag[:, 0]))
    return diag[:n], fills[: int(out[12])], out


@pytest.mark.parametrize("mode", [OFI, EWMA, HAWKES])
def test_loop_signal_equals_the_offline_causal_functions(day, mode):
    _, ev_ts, ev_side, ofi_ts, _, e = day
    diag, _, _ = run(day, mode, 0.5, 0.5)
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
    m = magnitude(a, trailing_mean(a, N), K)
    assert len(ts) > 30
    np.testing.assert_allclose(diag[:, 1], u, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(diag[:, 2], m, rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("mode", [OFI, EWMA, HAWKES])
def test_with_c_and_d_zero_every_overlay_trades_like_b1(day, mode):
    _, b1_fills, b1_out = run(day, NONE, 0.0, 0.0)
    _, fills, out = run(day, mode, 0.0, 0.0)
    assert np.array_equal(fills, b1_fills)
    assert np.array_equal(out, b1_out)
