"""The streamed reader must give exactly what convert_parts gives (Ilia, 2026-10-23): the
same parts for the same cuts, and the same concatenated events for any clean cuts."""

import gzip
from pathlib import Path

import numpy as np
import pytest
from synthetic import synthetic_day

from toxic_flow.data.convert import convert_parts
from toxic_flow.data.stream_convert import convert_parts_streamed


def same_info(a: dict, b: dict) -> bool:
    """Equal apart from the reader tag; JSON so that NaN (lot size on a synthetic day with
    one trade size) compares equal to NaN."""
    import json

    def strip(d):
        return {k: v for k, v in d.items() if k != "reader"}

    return json.dumps(strip(a), sort_keys=True, default=int) == json.dumps(
        strip(b), sort_keys=True, default=int
    )


@pytest.mark.parametrize("n_parts", [1, 3])
@pytest.mark.parametrize("chunk_bytes", [997, 1 << 20])
@pytest.mark.parametrize("mid_snapshot", [(20, 20), (25, 20)])
def test_same_parts_and_info_as_convert_parts(tmp_path, n_parts, chunk_bytes, mid_snapshot):
    # 997-byte chunks put snapshot blocks and part boundaries across chunk edges; (25, 20)
    # is the larger later snapshot of Q13.
    trades, depth = synthetic_day(tmp_path, mid_snapshot=mid_snapshot)
    old, old_info = convert_parts(trades, depth, n_parts=n_parts)
    new, new_info = convert_parts_streamed(trades, depth, n_parts=n_parts, chunk_bytes=chunk_bytes)
    assert len(new) == len(old) == n_parts
    for a, b in zip(old, new, strict=True):
        assert a.dtype == b.dtype and np.array_equal(a, b)
    assert same_info(old_info, new_info), (old_info, new_info)


def test_concatenated_events_do_not_depend_on_the_part_count(tmp_path):
    trades, depth = synthetic_day(tmp_path, overtaking_row=True)
    old = np.concatenate(convert_parts(trades, depth, n_parts=1)[0])
    new = np.concatenate(convert_parts_streamed(trades, depth, n_parts=3, chunk_bytes=4096)[0])
    assert np.array_equal(old, new)


def test_sink_gets_each_part_and_nothing_is_kept(tmp_path):
    trades, depth = synthetic_day(tmp_path)
    got = []
    parts, info = convert_parts_streamed(trades, depth, n_parts=3, sink=lambda k, p: got.append(k))
    assert parts == [] and got == [0, 1, 2] and len(info["events_per_part"]) == 3


RAW_DAY = Path(__file__).resolve().parents[2] / "data" / "raw" / "2024-01-01"


@pytest.mark.slow
@pytest.mark.skipif(not RAW_DAY.exists(), reason="benchmark day not downloaded")
def test_real_slice_matches_convert_parts(tmp_path):
    from test_convert import head_gz

    depth, trades = tmp_path / "incremental_book_L2.csv.gz", tmp_path / "trades.csv.gz"
    count = iter(range(3_000_000))
    head_gz(RAW_DAY / "incremental_book_L2.csv.gz", depth, lambda _: next(count, None) is not None)
    with gzip.open(depth, "rt") as f:
        t_end = max(int(line.split(",")[2]) for line in list(f)[1:])
    head_gz(RAW_DAY / "trades.csv.gz", trades, lambda line: int(line.split(",")[2]) <= t_end)
    kw = {"n_parts": 4, "search_windows_us": (60_000_000,)}
    old, old_info = convert_parts(trades, depth, **kw)
    new, new_info = convert_parts_streamed(trades, depth, chunk_bytes=1 << 20, **kw)
    assert all(np.array_equal(a, b) for a, b in zip(old, new, strict=True))
    assert same_info(old_info, new_info)
