"""AC1.4 and AC1.5: prints at one exchange timestamp and side become one market-order event."""

import gzip

import polars as pl
import pytest

from toxic_flow.events.market_orders import SCHEMA, collapse, write_events

HEADER = "exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n"


def trades_csv(tmp_path, rows):
    path = tmp_path / "trades.csv.gz"
    with gzip.open(path, "wt") as f:
        f.write(HEADER)
        for ts, local, side, px, qty in rows:
            f.write(f"binance-futures,BTCUSDT,{ts},{local},1,{side},{px},{qty}\n")
    return path


def test_ac1_4_three_prints_one_timestamp_one_side_become_one_event(tmp_path):
    path = trades_csv(
        tmp_path,
        [
            (1000, 1500, "buy", 100.0, 1.0),
            (1000, 1500, "buy", 100.1, 2.0),
            (1000, 1600, "buy", 100.2, 3.0),
        ],
    )
    events, stats = collapse(path)
    assert len(events) == 1
    e = events.row(0, named=True)
    assert e["side"] == "b"
    assert e["size"] == pytest.approx(6.0)
    assert e["vwap"] == pytest.approx((100.0 * 1 + 100.1 * 2 + 100.2 * 3) / 6)
    assert e["n_prints"] == 3
    assert e["levels"] == 3
    assert e["exch_ts"] == 1000 * 1000  # microseconds to nanoseconds, as hftbacktest
    assert e["local_ts"] == 1600 * 1000  # complete only when its last print has arrived
    assert stats["prints"] == 3 and stats["events"] == 1


def test_ac1_4_opposite_sides_at_one_timestamp_stay_two_events(tmp_path):
    path = trades_csv(tmp_path, [(1000, 1500, "buy", 100.0, 1.0), (1000, 1500, "sell", 99.9, 2.0)])
    events, _ = collapse(path)
    assert sorted(events["side"].to_list()) == ["b", "s"]


def test_same_side_at_different_timestamps_stay_separate(tmp_path):
    path = trades_csv(
        tmp_path, [(1000, 1500, "sell", 100.0, 1.0), (1001, 1501, "sell", 100.0, 1.0)]
    )
    events, _ = collapse(path)
    assert len(events) == 2


def test_unknown_side_is_dropped_and_counted(tmp_path):
    path = trades_csv(
        tmp_path, [(1000, 1500, "unknown", 100.0, 1.0), (1001, 1501, "buy", 100.0, 1.0)]
    )
    events, stats = collapse(path)
    assert len(events) == 1 and stats["unknown_side"] == 1


def test_local_timestamp_offset_is_applied(tmp_path):
    path = trades_csv(tmp_path, [(1000, 900, "buy", 100.0, 1.0)])
    events, _ = collapse(path, local_offset_ns=200_000)
    assert events["local_ts"][0] == 900 * 1000 + 200_000


def test_ac1_5_event_table_is_parquet_with_the_schema(tmp_path):
    path = trades_csv(tmp_path, [(1000, 1500, "buy", 100.0, 1.0), (1002, 1502, "sell", 99.0, 2.0)])
    events, _ = collapse(path)
    out = write_events(events, tmp_path / "events.parquet")
    back = pl.read_parquet(out)
    assert back.columns == ["exch_ts", "local_ts", "side", "size", "vwap", "n_prints", "levels"]
    assert dict(back.schema) == SCHEMA
    assert back["local_ts"].is_sorted()
