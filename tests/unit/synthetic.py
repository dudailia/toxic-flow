"""Synthetic Tardis CSV days for tests: small, but with the features real days have."""

import gzip

import numpy as np

DEPTH_HEADER = "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n"
TRADE_HEADER = "exchange,symbol,timestamp,local_timestamp,id,side,price,amount\n"
T0 = 1_704_067_200_000_000  # 2024-01-01 00:00:00 UTC in microseconds


def write_gz(path, header, rows):
    with gzip.open(path, "wt") as f:
        f.write(header)
        f.writelines(rows)


def snapshot_rows(ts, n_bid=20, n_ask=20):
    rows = []
    for side, sign, n in (("bid", -1, n_bid), ("ask", 1, n_ask)):
        for i in range(n):
            px = 42_000.0 + sign * (0.05 + 0.1 * i)
            rows.append(f"binance-futures,BTCUSDT,{ts},{ts + 900},true,{side},{px:.1f},1.5\n")
    return rows


def synthetic_day(tmp_path, mid_snapshot=(20, 20), seed=7, overtaking_row=False):
    """One timeline of depth updates and trades with a start-of-day snapshot, a mid-day
    snapshot, negative and reordering latencies, and a few quiet gaps where a clean cut
    exists. With overtaking_row, a book update sent just after the mid-day snapshot
    arrives before it, as when the REST snapshot is slower than the websocket."""
    rng = np.random.default_rng(seed)
    depth, trades, ts = snapshot_rows(T0), [], T0
    for step in range(3000):
        ts += int(rng.integers(0, 4000))
        if step % 700 == 699:
            ts += 200_000  # 200 ms with nothing sent
        if step == 1500:
            depth += snapshot_rows(ts, *mid_snapshot)
            if overtaking_row:
                depth.append(
                    f"binance-futures,BTCUSDT,{ts + 100},{ts + 200},false,bid,41999.9,2.0\n"
                )
        local = ts + int(rng.integers(-300, 5000))
        if rng.random() < 0.15:
            side = ["buy", "sell", "unknown"][int(rng.integers(0, 3))]
            trades.append(f"binance-futures,BTCUSDT,{ts},{local},{step},{side},42000.1,0.004\n")
        else:
            side = "bid" if rng.random() < 0.5 else "ask"
            px = 42_000.0 + (-1 if side == "bid" else 1) * (0.05 + 0.1 * int(rng.integers(0, 30)))
            qty = 0.0 if rng.random() < 0.2 else round(float(rng.random() * 3), 3)
            depth.append(f"binance-futures,BTCUSDT,{ts},{local},false,{side},{px:.1f},{qty}\n")
    write_gz(tmp_path / "trades.csv.gz", TRADE_HEADER, trades)
    write_gz(tmp_path / "incremental_book_L2.csv.gz", DEPTH_HEADER, depth)
    return tmp_path / "trades.csv.gz", tmp_path / "incremental_book_L2.csv.gz"
