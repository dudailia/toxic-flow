"""v2 quoting rules (PREREGISTRATION.md section 4): B0 and B1 join the touch, and the
overlay steps back on the side the signal marks as toxic."""

import numpy as np
import pytest

from toxic_flow.strategies.touch import PULL, step_back, touch_quote

BB, BA = 1000, 1001
INF = np.inf


def test_b0_quotes_the_best_prices_whatever_the_inventory():
    assert touch_quote(BB, BA, 4, False, 0.0, 0.0, INF, 1, INF)[:4] == (BB, BA, True, True)


def test_b1_moves_both_quotes_one_tick_per_order_size_against_the_position():
    # A 10-tick spread leaves room for the skew without crossing.
    assert touch_quote(BB, BB + 10, 2, True, 0.0, 0.0, INF, 1, INF)[:2] == (BB - 2, BB + 8)
    # With one tick, a long position's lower ask would cross, so it stays at the best ask.
    assert touch_quote(BB, BA, 2, True, 0.0, 0.0, INF, 1, INF)[:2] == (BB - 2, BA)
    # Short 3: bid 1003 would cross the best ask, so it moves to one tick below it.
    assert touch_quote(BB, BA, -3, True, 0.0, 0.0, INF, 1, INF)[:2] == (BA - 1, BA + 3)
    # Long 3: the ask 998 would cross the best bid, so it moves to one tick above it.
    assert touch_quote(BB, BA, 3, True, 0.0, 0.0, INF, 1, INF)[:2] == (BB - 3, BB + 1)


@pytest.mark.parametrize("k", [1, 5])
def test_the_toxic_side_is_the_one_that_steps_back(k):
    # u above the threshold: buyers are arriving, so the ask is toxic and moves up k ticks.
    assert step_back(BB, BA, 0.6, 0.0, 0.5, k, INF) == (BB, BA + k, True, True, 1)
    # u below minus the threshold: sellers, so the bid moves down.
    assert step_back(BB, BA, -0.6, 0.0, 0.5, k, INF) == (BB - k, BA, True, True, -1)


def test_inside_the_threshold_nothing_moves():
    for u in (0.5, -0.5, 0.0, 0.49):
        assert step_back(BB, BA, u, 0.0, 0.5, 5, INF) == (BB, BA, True, True, 0)


def test_pull_leaves_the_toxic_side_unquoted():
    assert step_back(BB, BA, 0.9, 0.0, 0.5, PULL, INF)[2:] == (True, False, 1)
    assert step_back(BB, BA, -0.9, 0.0, 0.5, PULL, INF)[2:] == (False, True, -1)


def test_magnitude_rule_widens_both_sides_and_adds_to_the_step():
    assert step_back(BB, BA, 0.0, 0.95, 0.5, 5, 0.9) == (BB - 1, BA + 1, True, True, 0)
    assert step_back(BB, BA, 0.9, 0.95, 0.5, 5, 0.9) == (BB - 1, BA + 6, True, True, 1)
    assert step_back(BB, BA, 0.0, 0.9, 0.5, 5, 0.9)[:2] == (BB, BA)  # m must be above


def test_infinite_thresholds_never_act():
    for u, m in ((1.0, 1.0), (-1.0, 1.0)):
        assert step_back(BB, BA, u, m, INF, PULL, INF) == (BB, BA, True, True, 0)


def test_the_step_comes_before_the_cross_rule():
    # Short 3 puts the skewed bid above the best ask; a 1-tick step back from 1003 is 1002,
    # still crossing, so the cross rule sets it to one tick below the best ask.
    assert touch_quote(BB, BA, -3, True, -0.9, 0.0, 0.5, 1, INF)[:2] == (BA - 1, BA + 3)
