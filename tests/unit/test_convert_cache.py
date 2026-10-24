"""Converted days are a cache (Ilia, 2026-10-23): rebuilt from the hashed raw files on demand,
checked against a SHA-256 per part recorded in data/manifest.json, evicted after a day's runs
unless the disk has more than 30 GB free, and never built with less than 15 GB free."""

import json
import shutil
from collections import namedtuple

import numpy as np
import pytest
from synthetic import synthetic_day

import toxic_flow.data.convert as cv
from toxic_flow.data.download import DiskSpaceError, load_manifest, save_manifest, sha256_file

DAY = "2024-01-01"


def raw_day(tmp_path):
    """A synthetic day laid out as data/raw/<day>/ with its manifest."""
    trades, depth = synthetic_day(tmp_path)
    raw = tmp_path / "raw" / DAY
    raw.mkdir(parents=True)
    entries = []
    for src in (trades, depth):
        shutil.copy(src, raw / src.name)
        entries.append(
            {
                "date": DAY,
                "data_type": src.name.split(".")[0],
                "sha256": sha256_file(src),
                "bytes": src.stat().st_size,
            }
        )
    save_manifest(tmp_path / "m.json", entries)
    return {
        "raw_dir": tmp_path / "raw",
        "out_dir": tmp_path / "conv",
        "manifest": tmp_path / "m.json",
    }


def test_each_converted_part_has_its_sha256_in_the_manifest(tmp_path):
    kw = raw_day(tmp_path)
    dest = cv.convert_day(DAY, min_free=0, **kw)
    record = json.loads(kw["manifest"].read_text())["converted"][DAY]
    parts = sorted(dest.glob("part-*.npz"))
    assert set(record["parts"]) == {p.name for p in parts}
    for p in parts:
        assert record["parts"][p.name] == cv.part_sha256(np.load(p)["data"])
    assert len(load_manifest(kw["manifest"])) == 2  # the raw entries are untouched


def test_a_rebuild_must_match_the_recorded_hashes(tmp_path):
    kw = raw_day(tmp_path)
    cv.convert_day(DAY, min_free=0, **kw)
    assert cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"], keep_free=10**18)
    assert not (kw["out_dir"] / DAY / "convert.json").exists()
    cv.convert_day(DAY, min_free=0, **kw)  # same raw files, same parts
    m = json.loads(kw["manifest"].read_text())
    m["converted"][DAY]["events_sha256"] = "0" * 64  # as if the events had changed
    kw["manifest"].write_text(json.dumps(m))
    cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"], keep_free=10**18)
    with pytest.raises(cv.ConversionError, match="do not match"):
        cv.convert_day(DAY, min_free=0, **kw)
    assert not (kw["out_dir"] / DAY).exists()


def test_no_conversion_starts_without_room(tmp_path):
    kw = raw_day(tmp_path)
    with pytest.raises(DiskSpaceError, match="free"):
        cv.convert_day(DAY, min_free=10**18, **kw)
    assert not kw["out_dir"].exists() or not list(kw["out_dir"].iterdir())
    assert cv.MIN_FREE_TO_CONVERT == 12 * 10**9  # Ilia, 2026-10-23 (was 15 GB, then 1.5)


def test_eviction_keeps_the_day_when_the_disk_has_room(tmp_path, monkeypatch):
    kw = raw_day(tmp_path)
    dest = cv.convert_day(DAY, min_free=0, **kw)
    (dest / "ofi_contributions.npz").write_bytes(b"cache")
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(cv.shutil, "disk_usage", lambda _: usage(1, 1, 40 * 10**9))
    assert not cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"])
    assert (dest / "convert.json").exists()
    monkeypatch.setattr(cv.shutil, "disk_usage", lambda _: usage(1, 1, 20 * 10**9))
    assert cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"])
    assert not list(dest.glob("part-*.npz")) and not (dest / "convert.json").exists()
    assert (dest / "ofi_contributions.npz").exists()  # small caches stay
    assert cv.KEEP_FREE_AFTER_RUNS == 30 * 10**9


def test_eviction_refuses_a_day_without_recorded_hashes(tmp_path):
    kw = raw_day(tmp_path)
    cv.convert_day(DAY, min_free=0, **kw)
    m = json.loads(kw["manifest"].read_text())
    del m["converted"]
    kw["manifest"].write_text(json.dumps(m))
    with pytest.raises(cv.ConversionError, match="no recorded"):
        cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"], keep_free=10**18)


def test_the_downloader_keeps_the_converted_record(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"files": [], "converted": {DAY: {"parts": {"part-00.npz": "a"}}}}))
    save_manifest(path, [{"date": DAY, "data_type": "trades", "sha256": "b"}])
    m = json.loads(path.read_text())
    assert m["converted"][DAY]["parts"] == {"part-00.npz": "a"} and len(m["files"]) == 1


def test_peak_memory_estimate_matches_the_streamed_reader_measurements():
    # Measured with /usr/bin/time: 3.38 GB for 100.1M events (2024-01-01) and 3.91 GB for
    # 198.3M (2024-05-01). Events are estimated as rows times 1.08, above both days' ratio.
    assert cv.estimate_peak_bytes(int(100_128_234 / 1.08)) == pytest.approx(3.38e9, rel=0.01)
    assert cv.estimate_peak_bytes(int(198_258_877 / 1.08)) == pytest.approx(3.91e9, rel=0.01)
    assert cv.estimate_peak_bytes(184_565_000) < 4e9  # 2024-05-01's counted rows


def test_concatenated_events_hash_is_recorded_and_checked(tmp_path):
    kw = raw_day(tmp_path)
    dest = cv.convert_day(DAY, min_free=0, **kw)
    rec = json.loads(kw["manifest"].read_text())["converted"][DAY]
    files = json.loads((dest / "convert.json").read_text())["files"]
    assert rec["events_sha256"] == cv.events_sha256([np.load(dest / f)["data"] for f in files])


def test_a_day_over_the_memory_limit_is_refused_before_any_work(tmp_path, monkeypatch):
    kw = raw_day(tmp_path)
    monkeypatch.setattr(cv, "estimate_peak_bytes", lambda rows: 12e9)
    with pytest.raises(cv.MemoryGuardError, match="11"):
        cv.convert_day(DAY, min_free=0, **kw)
    assert not (kw["out_dir"] / DAY).exists()


def test_a_day_is_refused_when_memory_is_not_free_now(tmp_path, monkeypatch):
    kw = raw_day(tmp_path)
    monkeypatch.setattr(cv, "estimate_peak_bytes", lambda rows: 5e9)
    monkeypatch.setattr(cv, "available_memory_bytes", lambda: 4e9)
    with pytest.raises(cv.MemoryGuardError, match="available"):
        cv.convert_day(DAY, min_free=0, **kw)


def test_a_rebuild_with_other_parts_updates_the_part_record_and_can_be_evicted(tmp_path):
    # Same events in a different number of parts (another part size, or the old reader's
    # record): the events hash matches, so the part record is refreshed, and eviction works.
    kw = raw_day(tmp_path)
    cv.convert_day(DAY, min_free=0, events_per_part=10**9, **kw)  # one part
    cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"], keep_free=10**18)
    dest = cv.convert_day(DAY, min_free=0, events_per_part=500, **kw)  # several parts
    parts = sorted(p.name for p in dest.glob("part-*.npz"))
    assert len(parts) > 1
    rec = json.loads(kw["manifest"].read_text())["converted"][DAY]
    assert sorted(rec["parts"]) == parts
    assert cv.evict_converted(DAY, out_dir=kw["out_dir"], manifest=kw["manifest"], keep_free=10**18)
