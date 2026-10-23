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
