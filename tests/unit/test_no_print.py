"""engine.run.opposite_prints (Q50) on a hand-made raw trades file."""

import gzip

import numpy as np

from toxic_flow.engine import run


def test_opposite_prints_keeps_the_price_furthest_through_at_each_time(tmp_path, monkeypatch):
    day = "2025-01-01"  # a validation day: the test-day lock allows it
    (tmp_path / day).mkdir()
    rows = ["exchange,symbol,timestamp,local_timestamp,id,side,price,amount",
            "binance-futures,BTCUSDT,10,11,1,buy,100.1,1", "binance-futures,BTCUSDT,10,11,2,buy,100.3,1",
            "binance-futures,BTCUSDT,12,13,3,sell,99.9,1", "binance-futures,BTCUSDT,12,13,4,sell,99.7,1",
            "binance-futures,BTCUSDT,11,12,5,buy,100.0,1"]  # fmt: skip
    with gzip.open(tmp_path / day / "trades.csv.gz", "wt") as f:
        f.write("\n".join(rows) + "\n")
    monkeypatch.setattr(run, "RAW", tmp_path)
    run.opposite_prints.cache_clear()
    p = run.opposite_prints(day)
    run.opposite_prints.cache_clear()
    np.testing.assert_array_equal(p["b"][0], [10_000, 11_000])  # microseconds to ns
    np.testing.assert_array_equal(p["b"][1], [100.3, 100.0])
    np.testing.assert_array_equal(p["s"][0], [12_000])
    np.testing.assert_array_equal(p["s"][1], [99.7])
