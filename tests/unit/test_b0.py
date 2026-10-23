import pytest

from toxic_flow.strategies.b0_fixed import order_size, quote_ticks, sides_allowed


@pytest.mark.parametrize(
    "best_bid, best_ask, h, expected",
    [
        (100, 101, 1, (99, 102)),  # one-tick spread: mid is half a tick inside, rounds outward
        (100, 102, 1, (100, 102)),  # two-tick spread: mid on a tick
        (100, 101, 3, (97, 104)),
    ],
)
def test_quote_ticks_round_outward(best_bid, best_ask, h, expected):
    assert quote_ticks(best_bid, best_ask, h) == expected


def test_quote_ticks_never_cross_the_book():
    bid, ask = quote_ticks(100, 101, 1)
    assert bid < 101 and ask > 100


def test_sides_allowed_respects_inventory_cap():
    q = 0.003
    assert sides_allowed(0.0, q, 10) == (True, True)
    assert sides_allowed(10 * q, q, 10) == (False, True)
    assert sides_allowed(-10 * q, q, 10) == (True, False)
    assert sides_allowed(9 * q + 1e-12, q, 10) == (True, True)  # float noise is not a lot


def test_order_size_meets_min_notional_in_whole_lots():
    # 100 USDT at 42,300 is 0.00236 BTC, so 3 lots of 0.001.
    assert order_size(42_300.0, 0.001, 100.0) == pytest.approx(0.003)
    # Exactly at the boundary one lot is enough.
    assert order_size(100_000.0, 0.001, 100.0) == pytest.approx(0.001)


def synthetic_backtest(tmp_path, latency):
    """A synthetic day converted the study's way, in a backtest with the study's models."""
    import numpy as np
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
    from hftbacktest.data.utils.feed_order_latency import generate_order_latency
    from synthetic import synthetic_day

    from toxic_flow.data.convert import convert_parts

    trades, depth = synthetic_day(tmp_path)
    (data,), _ = convert_parts(trades, depth, n_parts=1)
    np.savez_compressed(tmp_path / "day.npz", data=data)
    asset = BacktestAsset().data([str(tmp_path / "day.npz")]).linear_asset(1.0)
    if latency == "feed":
        # A file path, not the array: hftbacktest keeps a raw pointer to an ndarray
        # argument without copying it, so a local array would be freed under it.
        lat_file = tmp_path / "latency.npz"
        generate_order_latency(str(tmp_path / "day.npz"), str(lat_file), resampling_ns=100_000_000)
        asset = asset.intp_order_latency(str(lat_file))
    else:
        asset = asset.constant_order_latency(latency, latency)
    asset = (
        asset.risk_adverse_queue_model()
        .no_partial_fill_exchange()
        .trading_value_fee_model(0.0, 0.0)
        .tick_size(0.05)
        .lot_size(0.001)
    )
    return HashMapMarketDepthBacktest([asset])


def run_window(hbt, start_s, end_s):
    import numpy as np
    from synthetic import T0

    from toxic_flow.strategies.b0_fixed import run_b0
    from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE

    out = np.zeros(13)
    t0 = T0 * 1000
    steps, fills = np.zeros(1000, STEP_DTYPE), np.zeros(1000, FILL_DTYPE)
    run_b0(
        hbt,
        1,
        0.001,
        100.0,
        10,
        t0 + start_s * 10**9,
        t0 + end_s * 10**9,
        100_000_000,
        steps,
        fills,
        out,
    )
    hbt.close()
    return out


@pytest.mark.slow
def test_run_b0_quotes_through_the_window(tmp_path):
    # Engine smoke run with the study's exchange and latency models. Catches loops that
    # never start: before its first elapse, hftbacktest's current_timestamp is i64 max.
    out = run_window(synthetic_backtest(tmp_path, "feed"), 1, 4)
    assert 25 <= out[0] <= 31  # about one quoted step per 100 ms of the 3 s window
    assert out[5] == pytest.approx(0.003)  # 100 USDT at about 42,000 is 3 lots


@pytest.mark.slow
def test_run_b0_one_order_per_side_when_latency_exceeds_the_step(tmp_path):
    # 250 ms each way is longer than the 100 ms step, so cancels and new orders are in
    # flight when the target moves. B0 must still hold at most one order per side.
    out = run_window(synthetic_backtest(tmp_path, 250_000_000), 1, 6)
    assert out[0] > 0
    assert out[6] == 1
    assert out[7] <= 10


@pytest.mark.slow
def test_run_b0_stops_deciding_at_quote_end_and_marks_there(tmp_path):
    from synthetic import T0

    out = run_window(synthetic_backtest(tmp_path, "feed"), 1, 4)
    end = T0 * 1000 + 4 * 10**9
    assert out[8] < end <= out[9] < end + 100_000_000


@pytest.mark.slow
def test_quote_presence_counts_only_orders_resting_in_the_book(tmp_path):
    # Section 6: the share of time both sides are quoted. At 250 ms each way, the first
    # orders are acknowledged 500 ms after they are sent, so the first five steps have
    # nothing resting in the book and must not count as quoted.
    import numpy as np
    from synthetic import T0

    from toxic_flow.strategies.b0_fixed import run_b0
    from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE

    hbt = synthetic_backtest(tmp_path, 250_000_000)
    out, t0 = np.zeros(13), T0 * 1000
    steps, fills = np.zeros(1000, STEP_DTYPE), np.zeros(1000, FILL_DTYPE)
    run_b0(hbt, 1, 0.001, 100.0, 10, t0 + 10**9, t0 + 6 * 10**9, 100_000_000, steps, fills, out)
    hbt.close()
    quoted = steps["both_quoted"][: int(out[0])]
    assert not quoted[:5].any()
    assert quoted[5:].any()
