"""The mid grid for the signal-information study reads only the past."""

import numpy as np

from toxic_flow.data.book import BBO_DTYPE
from toxic_flow.data.mids import mid_grid

S = 10**9


def test_the_mid_at_t_is_the_last_book_at_or_before_t():
    bbo = np.zeros(3, BBO_DTYPE)
    bbo["local_ts"] = [S, 2 * S, 3 * S]
    bbo["bid_px"] = [100.0, 101.0, 102.0]
    bbo["ask_px"] = [100.2, 101.2, 101.0]  # the last book is crossed
    ts, mid = mid_grid(bbo, 0, 4 * S, S // 2)
    assert np.isnan(mid[0]) and np.isnan(mid[1])  # before the first book
    assert mid[2] == 100.1 and mid[3] == 100.1  # 1 s and 1.5 s
    assert mid[4] == 101.1 and mid[5] == 101.1
    assert np.isnan(mid[6]) and np.isnan(mid[7])  # crossed
