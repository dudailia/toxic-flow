"""C2, the oracle (PREREGISTRATION.md section 10): u is the sign of the mid change over the
next 5 s. The series is forward-looking by design; the loop still reads only points at or
before now."""

import numpy as np
import pytest
from c2_oracle import oracle_series

from toxic_flow.data.book import BBO_DTYPE

S = 10**9


def test_oracle_u_is_the_sign_of_the_mid_change_five_seconds_ahead():
    bbo = np.zeros(4, BBO_DTYPE)
    bbo["local_ts"] = [0, 3 * S, 6 * S, 12 * S]
    bbo["bid_px"] = [100.0, 101.0, 99.0, 99.0]
    bbo["ask_px"] = bbo["bid_px"] + 0.1
    grid = np.array([0, 2 * S, 7 * S, 20 * S], np.int64)
    ts, u, m = oracle_series(bbo, grid, horizon_s=5.0)
    # t=0: mid at 5 s (row of 3 s) is above; t=2 s: at 7 s (row of 6 s) below;
    # t=7 s: at 12 s unchanged; t=20 s: no mid 5 s later, so no information.
    assert list(u) == [1.0, -1.0, 0.0, 0.0]
    assert np.all(m == 0.0) and np.array_equal(ts, grid)


@pytest.mark.slow
def test_the_loop_reads_the_oracle_series_only_up_to_now(tmp_path):
    from c2_oracle import run_loop_on_file
    from synthetic import synthetic_day

    from toxic_flow.data.convert import convert_parts

    trades, depth = synthetic_day(tmp_path)
    (data,), _ = convert_parts(trades, depth, n_parts=1)
    np.savez_compressed(tmp_path / "day.npz", data=data)
    ts = np.arange(data["local_ts"].min(), data["local_ts"].max(), 50_000_000, dtype=np.int64)
    u = np.where(np.arange(len(ts)) % 2 == 0, 1.0, -1.0)
    diag = run_loop_on_file(tmp_path / "day.npz", ts, u, np.zeros(len(ts)))
    for now, u_loop in diag[:, :2]:
        i = np.searchsorted(ts, int(now), side="right") - 1
        assert u_loop == (u[i] if i >= 0 else 0.0)


def test_oracle_u_has_the_sign_of_the_future_mid_change_on_a_random_book():
    # Item 1 of the M4 diagnosis: brute force against an irregular random-walk book.
    rng = np.random.default_rng(1729)
    n = 2000
    bbo = np.zeros(n, BBO_DTYPE)
    bbo["local_ts"] = np.cumsum(rng.integers(1, 3 * S // 10, n))
    bbo["bid_px"] = 100.0 + np.cumsum(rng.choice([-0.1, 0.0, 0.1], n))
    bbo["ask_px"] = bbo["bid_px"] + 0.1
    grid = np.arange(bbo["local_ts"][0], bbo["local_ts"][-1], S // 10, dtype=np.int64)
    _, u, _ = oracle_series(bbo, grid, horizon_s=5.0)
    mid = (bbo["bid_px"] + bbo["ask_px"]) / 2
    for t, ut in zip(grid[::7], u[::7], strict=True):
        if t + 5 * S > bbo["local_ts"][-1]:
            assert ut == 0.0
            continue
        now = mid[np.flatnonzero(bbo["local_ts"] <= t)[-1]]
        later = mid[np.flatnonzero(bbo["local_ts"] <= t + 5 * S)[-1]]
        assert ut == np.sign(later - now)


@pytest.mark.slow
def test_the_loop_moves_its_quotes_up_for_u_plus_one_and_down_for_u_minus_one(tmp_path):
    # Item 1 of the M4 diagnosis, end to end in the loop: with c = 1, m = 0 and touch
    # quotes, every recorded quote must equal the section 4 overlay of the step's own book
    # and inventory, centre = r + u * half, so u = +1 lifts both quotes and u = -1 lowers
    # them. touch needs no GLFT fit, so a short synthetic day is enough.
    from c2_oracle import run_loop_on_file
    from synthetic import synthetic_day

    from toxic_flow.data.convert import convert_parts

    trades, depth = synthetic_day(tmp_path)
    (data,), _ = convert_parts(trades, depth, n_parts=1)
    np.savez_compressed(tmp_path / "day.npz", data=data)
    ts = np.arange(data["local_ts"].min(), data["local_ts"].max(), 50_000_000, dtype=np.int64)
    one = np.ones(len(ts))
    for u in (1.0, -1.0):
        _, st, qty = run_loop_on_file(
            tmp_path / "day.npz", ts, u * one, 0 * one, touch=True, with_steps=True
        )
        bb, ba = st["best_bid_tick"], st["best_ask_tick"]
        half = 0.5 * (ba - bb)
        r = (bb + ba) / 2 - st["position"] / qty
        quoted = np.isfinite(st["bid_tick"])
        assert quoted.sum() > 10
        want_bid = np.minimum(np.floor(r + u * half - half), ba - 1)
        want_ask = np.maximum(np.ceil(r + u * half + half), bb + 1)
        assert np.array_equal(st["bid_tick"][quoted], want_bid[quoted])
        ask = np.isfinite(st["ask_tick"])
        assert np.array_equal(st["ask_tick"][ask], want_ask[ask])
        # And the direction: against the u = 0 quote of the same step.
        no_signal_bid = np.minimum(np.floor(r - half), ba - 1)
        assert np.all(np.sign(st["bid_tick"][quoted] - no_signal_bid[quoted]) * u >= 0)
