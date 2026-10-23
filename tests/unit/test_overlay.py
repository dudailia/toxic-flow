"""Overlay prices (PREREGISTRATION.md section 4): with c = d = 0 every overlay is B1."""

import numpy as np

from toxic_flow.strategies.overlay import overlay_ticks


def test_c_and_d_zero_reduce_to_b1():
    r, half = 1000.3, 1.7
    assert overlay_ticks(r, half, 0.9, 0.8, 0.0, 0.0, 999, 1001) == (
        np.floor(r - half),
        np.ceil(r + half),
    )


def test_direction_moves_the_centre_by_c_u_delta():
    bid, ask = overlay_ticks(1000.0, 2.0, 1.0, 0.0, 1.0, 0.0, 990, 1010)
    assert (bid, ask) == (1000.0, 1004.0)  # centre 1002


def test_magnitude_widens_both_sides_by_d_m_delta():
    bid, ask = overlay_ticks(1000.0, 2.0, 0.0, 1.0, 0.0, 0.5, 990, 1010)
    assert (bid, ask) == (997.0, 1003.0)  # half spread 2 * 1.5 = 3


def test_cross_guard_keeps_quotes_off_the_other_side():
    bid, ask = overlay_ticks(1000.0, 0.4, 1.0, 0.0, 5.0, 0.0, 1001, 1002)
    assert bid == 1001 and ask >= 1002  # bid at or above the ask moves to ask - 1
