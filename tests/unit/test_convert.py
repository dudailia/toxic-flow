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
from synthetic import synthetic_day

from toxic_flow.data.convert import ConversionError, convert_parts


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


def all_exch_ts(trades, depth):
    import toxic_flow.data.convert as cv

    t_ts = cv.read_trades(trades, 1 << 20)["exch_ts"]
    return np.sort(np.concatenate([t_ts, cv.read_depth(depth, 1 << 20)["exch_ts"]]))


def test_cut_while_messages_in_flight_is_caught(tmp_path, monkeypatch):
    # Cutting mid-traffic changes the merged order, so convert_parts re-checks every cut
    # it uses and refuses one where a message sent before it arrives after it.
    import toxic_flow.data.convert as cv

    trades, depth = synthetic_day(tmp_path)
    e = all_exch_ts(trades, depth)
    monkeypatch.setattr(cv, "find_cuts", lambda *a: [int(e[1000]), int(e[2000])])
    with pytest.raises(ConversionError):
        convert_parts(trades, depth, n_parts=3)


def test_cuts_out_of_order_raise(tmp_path, monkeypatch):
    import toxic_flow.data.convert as cv

    trades, depth = synthetic_day(tmp_path)
    good, _ = convert_parts(trades, depth, n_parts=3)
    cuts = convert_parts(trades, depth, n_parts=3)[1]["cuts"]
    monkeypatch.setattr(cv, "find_cuts", lambda *a: [cuts[1], cuts[0]])
    with pytest.raises(ConversionError):
        convert_parts(trades, depth, n_parts=3)


def test_overtaking_row_after_snapshot_matches(tmp_path):
    # correct_event_order splits rows whose two orders disagree, so snapshot rows can
    # appear twice in the output; the snapshot check must not count those copies.
    trades, depth = synthetic_day(tmp_path, overtaking_row=True)
    expected = tardis.convert([str(trades), str(depth)])
    for n_parts in (1, 3):
        parts, _ = convert_parts(trades, depth, n_parts=n_parts)
        assert np.array_equal(np.concatenate(parts), expected)


def test_find_cuts_keeps_a_snapshot_with_its_closing_row():
    # A block at 45 is emitted when its closing row (sent at 60) is read, so no cut may
    # fall in (45, 60]: the block would end its part unemitted.
    from toxic_flow.data.convert import find_cuts

    dt = np.dtype([("exch_ts", "i8"), ("local_ts", "i8")])
    depth = np.zeros(101, dt)
    depth["exch_ts"] = np.arange(101)
    depth["local_ts"] = depth["exch_ts"]  # no latency, so every gap is a clean cut
    trades = depth[:1].copy()
    assert find_cuts(trades, depth, 2, (100,), [(45, 45, 60)]) == [45]


def test_inferred_counts_are_rows_not_events(tmp_path):
    trades, depth = synthetic_day(tmp_path, overtaking_row=True)
    _, info = convert_parts(trades, depth, n_parts=1)
    with gzip.open(depth, "rt") as f:
        book_rows = sum(1 for _ in f) - 1
    with gzip.open(trades, "rt") as f:
        trade_rows = sum(1 for _ in f) - 1
    assert info["inferred"]["book_rows"] == book_rows
    assert info["inferred"]["trade_rows"] == trade_rows
    assert info["inferred"]["tick_size"] == pytest.approx(0.1)


def test_no_clean_cut_raises(tmp_path):
    trades, depth = synthetic_day(tmp_path)
    with pytest.raises(ConversionError):
        convert_parts(trades, depth, n_parts=3, search_windows_us=(1_000,))


@pytest.mark.parametrize("n_parts", [1, 2])
def test_a_later_snapshot_larger_than_an_earlier_one_is_kept_whole(tmp_path, n_parts):
    # hftbacktest's one-shot convert would cut this 25-level snapshot to 20 levels, as it
    # reslices its buffers to each block. One call per block keeps every level (Q13);
    # convert_parts itself checks the emitted rows against the full block sizes.
    from hftbacktest.types import DEPTH_SNAPSHOT_EVENT

    trades, depth = synthetic_day(tmp_path, mid_snapshot=(25, 20))
    parts, info = convert_parts(trades, depth, n_parts=n_parts)
    data = np.concatenate(parts)
    snap = (data["ev"] & 0xFF) == DEPTH_SNAPSHOT_EVENT
    rows = sum(b + a for b, a in info["snapshot_levels_bid_ask"])
    # correct_event_order may write a row twice (EXCH and LOCAL), so at least that many.
    assert snap.sum() >= rows


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
    parts, info = convert_parts(trades, depth, n_parts=4, search_windows_us=(60_000_000,))
    got = np.concatenate(parts)
    assert len(info["cuts"]) == 3
    assert np.array_equal(got, expected)


def test_failed_conversion_leaves_no_staging_directory(tmp_path, monkeypatch):
    import shutil

    from hftbacktest.types import event_dtype

    import toxic_flow.data.convert as cv
    from toxic_flow.data.download import save_manifest, sha256_file

    trades, depth = synthetic_day(tmp_path)
    raw = tmp_path / "raw" / "2024-01-01"
    raw.mkdir(parents=True)
    entries = []
    for src in (trades, depth):
        shutil.copy(src, raw / src.name)
        entries.append(
            {"date": "2024-01-01", "data_type": src.name.split(".")[0], "sha256": sha256_file(src)}
        )
    save_manifest(tmp_path / "m.json", entries)

    def fail_after_one_part(*args, sink=None, **kwargs):
        sink(0, np.zeros(3, event_dtype))
        raise ConversionError("simulated")

    import toxic_flow.data.stream_convert as sc

    monkeypatch.setattr(cv, "available_memory_bytes", lambda: 64e9)  # not the machine's

    monkeypatch.setattr(sc, "convert_parts_streamed", fail_after_one_part)  # convert_day's reader
    out = tmp_path / "converted"
    with pytest.raises(ConversionError):
        cv.convert_day(
            "2024-01-01",
            raw_dir=tmp_path / "raw",
            out_dir=out,
            manifest=tmp_path / "m.json",
            min_free=0,  # a synthetic day of a few KB; the 15 GB guard is tested apart
        )
    assert not list(out.iterdir())


def test_snapshot_block_span_is_min_to_max():
    from toxic_flow.data.convert import _snapshot_blocks

    exch = np.array([100, 50, 120, 130], np.int64)
    side = np.array([1, -1, 1, 1], np.int8)
    snap = np.array([1, 1, 1, 0], np.int8)
    lo, hi, close, nb, na, _ = _snapshot_blocks(exch, side, snap, 1000)
    assert (lo[0], hi[0], close[0], nb[0], na[0]) == (50, 120, 130, 2, 1)


def test_header_only_file_raises_conversion_error(tmp_path):
    from synthetic import TRADE_HEADER, write_gz

    _, depth = synthetic_day(tmp_path)
    write_gz(tmp_path / "trades.csv.gz", TRADE_HEADER, [])
    with pytest.raises(ConversionError):
        convert_parts(tmp_path / "trades.csv.gz", depth, n_parts=1)


def test_order_part_pads_the_indexes_correct_event_order_reads_past(tmp_path):
    # hftbacktest's correct_event_order reads data[index[n]] one step past the end of each
    # index before its bounds check; unpadded that read can segfault (2024-02-01). Padding
    # with row 0 makes it a valid read, and the output must not change.
    from hftbacktest.data.validation import correct_event_order

    import toxic_flow.data.convert as cv

    trades, depth = synthetic_day(tmp_path, overtaking_row=True)
    t = cv.read_trades(trades, 1 << 20)
    d = cv.read_depth(depth, 1 << 20)
    tmp = cv.part_events(t, d, 0)
    unpadded = correct_event_order(
        tmp.copy(),
        np.argsort(tmp["exch_ts"], kind="mergesort"),
        np.argsort(tmp["local_ts"], kind="mergesort"),
    )
    assert np.array_equal(cv.order_part(tmp.copy(), 0), unpadded)
    assert len(cv._padded(np.arange(3))) == 4 and cv._padded(np.arange(3))[-1] == 0
