import numpy as np
import pytest

from toxic_flow.data.validate import infer_increment


def test_infer_increment_is_most_common_gap():
    step, off = infer_increment(np.array([42314.0, 42314.1, 42314.2, 42315.3, 42314.0]))
    assert step == pytest.approx(0.1)
    assert off == 0


def test_rare_off_grid_value_is_counted_not_taken_as_the_tick():
    # 2024-01-01 has a few hundred book rows on a 0.01 grid; they must not set the tick.
    values = np.array([42314.0, 42314.1, 42314.2, 42314.3, 42314.35, 42314.35])
    counts = np.array([5, 5, 5, 5, 1, 1])
    step, off = infer_increment(values, counts)
    assert step == pytest.approx(0.1)
    assert off == 2


def test_infer_increment_lot_sizes():
    step, off = infer_increment(np.array([0.003, 0.001, 0.004, 0.002, 1.25]))
    assert step == pytest.approx(0.001)
    assert off == 0


def test_largest_gap_counts_from_the_window_edges():
    from toxic_flow.data.validate import largest_gap

    ts = np.array([5, 7, 30, 31], np.int64) * 10**9
    gap_s, at = largest_gap(ts, start=0, end=40 * 10**9)
    assert gap_s == 23.0 and at == 7 * 10**9
    gap_s, at = largest_gap(np.array([], np.int64), start=0, end=10 * 10**9)
    assert gap_s == 10.0 and at == 0  # an empty stream is one gap across the window


def test_latency_quantiles_in_ms():
    from toxic_flow.data.validate import latency_quantiles_ms

    q = latency_quantiles_ms(np.arange(1, 101, dtype=np.int64) * 1_000_000)
    assert q["p50"] == 50.5 and q["max"] == 100.0


def test_quality_report_on_a_converted_synthetic_day(tmp_path):
    import gzip

    from synthetic import T0, synthetic_day

    from toxic_flow.data.convert import convert_parts
    from toxic_flow.data.validate import quality_report

    trades, depth = synthetic_day(tmp_path)
    (data,), _ = convert_parts(trades, depth, n_parts=1)
    np.savez_compressed(tmp_path / "part-00.npz", data=data)
    window = (T0 * 1000 + 500_000_000, T0 * 1000 + 6_000_000_000)
    rep = quality_report([tmp_path / "part-00.npz"], 0.05, 0.001, window)
    with gzip.open(depth, "rt") as f:
        book_rows = sum(1 for line in f if ",false," in line)
    with gzip.open(trades, "rt") as f:
        trade_rows = sum(1 for _ in f) - 1
    assert rep["book_updates"] == book_rows
    assert rep["trades"] == trade_rows
    assert rep["crossed_book_batches"] == 0
    assert rep["largest_gap_s"]["book"] >= 0.2  # the generator leaves 200 ms quiet gaps
    assert set(rep["feed_latency_ms"]["book"]) == {"p50", "p90", "p99", "max"}


def test_largest_gap_over_sorted_pieces_equals_the_whole_day():
    # Received events are in local-time order within each part and across parts, so the
    # gap can be found part by part without holding the whole day.
    import numpy as np

    from toxic_flow.data.validate import largest_gap, largest_gap_sorted

    rng = np.random.default_rng(3)
    t = np.sort(rng.integers(0, 10**12, 5000))
    t[2000:2100] = t[1999]  # ties
    for start, end in ((0, 10**12), (10**11, 9 * 10**11), (t[100], t[100])):
        pieces = np.split(t, [7, 1500, 1500, 4999])
        assert largest_gap_sorted(pieces, start, end) == largest_gap(t, start, end)
    assert largest_gap_sorted([np.array([], np.int64)], 5, 15) == largest_gap(
        np.array([], np.int64), 5, 15
    )


def test_latency_quantiles_from_value_counts_equal_numpy_percentile():
    import numpy as np

    from toxic_flow.data.validate import LatencyCounts, latency_quantiles_ms

    rng = np.random.default_rng(5)
    lat = rng.lognormal(8, 1, 100_001).astype(np.int64) * 1000  # whole microseconds, in ns
    acc = LatencyCounts()
    for piece in np.array_split(lat, 7):
        acc.add(piece)
    assert acc.quantiles_ms() == latency_quantiles_ms(lat)
