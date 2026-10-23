"""Best bid and offer replayed through hftbacktest's own book."""

import numpy as np
import pytest
from hftbacktest import (
    BUY_EVENT,
    DEPTH_EVENT,
    DEPTH_SNAPSHOT_EVENT,
    EXCH_EVENT,
    LOCAL_EVENT,
    SELL_EVENT,
)
from hftbacktest.types import event_dtype

from toxic_flow.data.book import replay_bbo

S = 1_000_000_000
F = EXCH_EVENT | LOCAL_EVENT


def events_file(tmp_path, rows):
    data = np.zeros(len(rows), event_dtype)
    for i, (ev, ts, px, qty) in enumerate(rows):
        data[i]["ev"], data[i]["exch_ts"], data[i]["local_ts"] = ev, ts, ts
        data[i]["px"], data[i]["qty"] = px, qty
    path = tmp_path / "day.npz"
    np.savez_compressed(path, data=data)  # a path: hftbacktest would not copy an array
    return path


def test_replay_counts_a_crossed_book_and_the_empty_side_it_leaves(tmp_path):
    # hftbacktest's book never shows best bid >= best ask: a crossing bid moves the best
    # ask past it (update_bid_depth), here to "none", and the ask side stays empty until
    # the next ask update. The replay counts the hidden overlap and the one-sided batches.
    path = events_file(
        tmp_path,
        [
            (F | DEPTH_SNAPSHOT_EVENT | BUY_EVENT, 1 * S, 100.0, 2.0),
            (F | DEPTH_SNAPSHOT_EVENT | SELL_EVENT, 1 * S, 100.2, 3.0),
            (F | DEPTH_EVENT | BUY_EVENT, 2 * S, 100.1, 1.0),  # new best bid
            (F | DEPTH_EVENT | BUY_EVENT, 3 * S, 100.3, 1.0),  # bid above the ask: crossed
            (F | DEPTH_EVENT | BUY_EVENT, 4 * S, 100.3, 0.0),  # gone; ask side still empty
            (F | DEPTH_EVENT | SELL_EVENT, 5 * S, 100.2, 4.0),  # ask update restores it
            (F | DEPTH_EVENT | BUY_EVENT, 6 * S, 99.0, 1.0),  # the last batch is not returned
        ],
    )
    bbo, stats = replay_bbo([path], tick_size=0.1, lot_size=0.001, chunk=2)
    assert stats["batches"] == 5
    assert stats["crossed"] == 1  # the 3 s batch: an ask level at or below the best bid
    assert stats["one_sided"] == 2  # 3 s and 4 s
    assert list(bbo["local_ts"]) == [1 * S, 2 * S, 5 * S]  # rows need both sides
    # Prices come back as tick * tick_size, so compare them approximately.
    assert bbo["bid_px"][1] == pytest.approx(100.1) and bbo["bid_qty"][1] == 1.0
    assert bbo["ask_px"][2] == pytest.approx(100.2) and bbo["ask_qty"][2] == 4.0
