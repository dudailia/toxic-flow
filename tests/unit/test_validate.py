import numpy as np
import pytest

from toxic_flow.data.validate import infer_increment


def test_infer_increment_is_most_common_gap():
    step, off = infer_increment(np.array([42314.0, 42314.1, 42314.2, 42315.3, 42314.0]))
    assert step == pytest.approx(0.1)
    assert off == 0


def test_rare_off_grid_value_is_counted_not_taken_as_the_tick():
    # 2024-01-01 has a few hundred book rows on a 0.01 grid; they must not set the tick.
    values = np.array([42314.0, 42314.1, 42314.2, 42314.3, 42314.35, 42314.35])
    counts = np.array([5, 5, 5, 5, 1, 1])
    step, off = infer_increment(values, counts)
    assert step == pytest.approx(0.1)
    assert off == 2


def test_infer_increment_lot_sizes():
    step, off = infer_increment(np.array([0.003, 0.001, 0.004, 0.002, 1.25]))
    assert step == pytest.approx(0.001)
    assert off == 0
