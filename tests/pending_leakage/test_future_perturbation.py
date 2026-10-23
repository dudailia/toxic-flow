"""AC3.1: replacing every event after t with random events leaves each signal unchanged at
every decision time up to t. Pending: to move into tests/leakage/ (protected) by Ilia."""

import numpy as np
import pytest

from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_online import hawkes_signal

S = 10**9
CUT = 50 * S
DECISIONS = np.arange(0, 100 * S, 100_000_000, dtype=np.int64)
MU, ALPHA, BETA = np.array([0.6, 0.4]), np.array([[0.8, 0.3], [0.2, 0.7]]), 2.0


def random_events(rng, start, end, n):
    ts = np.sort(rng.integers(start, end, n)).astype(np.int64)
    return ts, rng.integers(0, 2, n)


def perturbed(seed):
    rng = np.random.default_rng(seed)
    ts, side = random_events(rng, 0, 100 * S, 3000)
    keep = ts <= CUT
    new_ts, new_side = random_events(rng, CUT + 1, 100 * S, 5000)  # different count too
    return (ts, side), (np.concatenate([ts[keep], new_ts]), np.concatenate([side[keep], new_side]))


SIGNALS = {
    "ewma_tau_1s": lambda ts, side: ewma_at(ts, side, DECISIONS, 1.0),
    "ewma_tau_30s": lambda ts, side: ewma_at(ts, side, DECISIONS, 30.0),
    "hawkes": lambda ts, side: hawkes_signal(ts, side, DECISIONS, MU, ALPHA, BETA),
}


@pytest.mark.parametrize("name", sorted(SIGNALS))
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ac3_1_future_events_do_not_change_the_signal_up_to_t(name, seed):
    (ts, side), (ts2, side2) = perturbed(seed)
    before = SIGNALS[name](ts, side)
    after = SIGNALS[name](ts2, side2)
    past = DECISIONS <= CUT
    for x, y in zip(before, after, strict=True):
        assert np.array_equal(x[past], y[past])
        assert not np.array_equal(x[~past], y[~past])  # the perturbation did reach the future


def test_the_perturbation_test_catches_a_one_second_look_ahead():
    (ts, side), (ts2, side2) = perturbed(1)

    def peeking(ts, side):
        return ewma_at(ts, side, DECISIONS + S, 1.0)  # sees events up to t + 1 s

    past = DECISIONS <= CUT
    assert not np.array_equal(peeking(ts, side)[0][past], peeking(ts2, side2)[0][past])
