"""convert_parts must give exactly what hftbacktest's own tardis.convert gives.

convert_parts changes only how the CSV is read (streamed in chunks, unused text columns
dropped) and splits the day into parts at instants where no message is in flight, so a
full BTCUSDT day fits in memory. Every conversion step is hftbacktest's. The parts,
concatenated, must equal the one-shot conversion.
"""

import gzip
from pathlib import Path

import numpy as np
import pytest
from hftbacktest.data.utils import tardis

from toxic_flow.data.convert import ConversionError, convert_parts

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


def synthetic_day(tmp_path, mid_snapshot=(20, 20), seed=7):
    """One timeline of depth updates and trades with a start-of-day snapshot, a mid-day
    snapshot, negative and reordering latencies, and a few quiet gaps where a clean cut
    exists."""
    rng = np.random.default_rng(seed)
    depth, trades, ts = snapshot_rows(T0), [], T0
    for step in range(3000):
        ts += int(rng.integers(0, 4000))
        if step % 700 == 699:
            ts += 200_000  # 200 ms with nothing sent
        if step == 1500:
            depth += snapshot_rows(ts, *mid_snapshot)
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


@pytest.mark.parametrize("n_parts", [1, 3])
@pytest.mark.parametrize("chunk_bytes", [997, 1 << 20])
def test_parts_concatenate_to_hftbacktest_tardis_convert(tmp_path, n_parts, chunk_bytes):
    trades, depth = synthetic_day(tmp_path)
    expected = tardis.convert([str(trades), str(depth)])
    parts, info = convert_parts(trades, depth, n_parts=n_parts, chunk_bytes=chunk_bytes)
    assert len(parts) == n_parts
    got = np.concatenate(parts)
    assert got.dtype == expected.dtype
    assert np.array_equal(got, expected)
    assert len(info["cuts"]) == n_parts - 1


def test_cut_while_messages_in_flight_would_differ(tmp_path, monkeypatch):
    # Why cuts must be clean: cutting mid-traffic changes the merged order.
    import toxic_flow.data.convert as cv

    trades, depth = synthetic_day(tmp_path)
    expected = tardis.convert([str(trades), str(depth)])
    t_ts = cv.read_trades(trades, 1 << 20)["exch_ts"]
    e = np.sort(np.concatenate([t_ts, cv.read_depth(depth, 1 << 20)["exch_ts"]]))
    monkeypatch.setattr(cv, "find_cuts", lambda *a: [int(e[1000]), int(e[2000])])
    parts, _ = convert_parts(trades, depth, n_parts=3)
    got = np.concatenate(parts)
    assert len(got) != len(expected) or not np.array_equal(got, expected)


def test_no_clean_cut_raises(tmp_path):
    trades, depth = synthetic_day(tmp_path)
    with pytest.raises(ConversionError):
        convert_parts(trades, depth, n_parts=3, search_window_us=1_000)


def test_later_snapshot_larger_than_first_raises(tmp_path):
    # hftbacktest's one-shot convert would silently truncate this snapshot to 20 levels.
    trades, depth = synthetic_day(tmp_path, mid_snapshot=(25, 20))
    with pytest.raises(ConversionError):
        convert_parts(trades, depth, n_parts=1)


RAW_DAY = Path(__file__).resolve().parents[2] / "data" / "raw" / "2024-01-01"


def head_gz(src, dest, keep):
    """Copy the header and the leading rows of src for which keep(row) is true."""
    with gzip.open(src, "rt") as f, gzip.open(dest, "wt") as out:
        out.write(f.readline())
        for line in f:
            if not keep(line):
                break
            out.write(line)


@pytest.mark.slow
@pytest.mark.skipif(not RAW_DAY.exists(), reason="benchmark day not downloaded")
def test_real_slice_matches_tardis_convert(tmp_path):
    # The first 3M book rows of 2024-01-01 (about the first 40 minutes) and the trades
    # sent before the last of them: real snapshot, real latencies, real cut search.
    depth, trades = tmp_path / "incremental_book_L2.csv.gz", tmp_path / "trades.csv.gz"
    count = iter(range(3_000_000))
    head_gz(RAW_DAY / "incremental_book_L2.csv.gz", depth, lambda _: next(count, None) is not None)
    with gzip.open(depth, "rt") as f:
        t_end = max(int(line.split(",")[2]) for line in list(f)[1:])
    head_gz(RAW_DAY / "trades.csv.gz", trades, lambda line: int(line.split(",")[2]) <= t_end)

    expected = tardis.convert([str(trades), str(depth)])
    parts, info = convert_parts(trades, depth, n_parts=4, search_window_us=60_000_000)
    got = np.concatenate(parts)
    assert len(info["cuts"]) == 3
    assert np.array_equal(got, expected)
