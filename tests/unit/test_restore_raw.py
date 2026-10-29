"""scripts/restore_raw.py: removed training and validation raw files come back through the
downloader as the same bytes, and no test day is ever removed or requested."""

import sys
from pathlib import Path

import pytest
from test_download import BODY, client, serve

from toxic_flow.data.download import download_day, sha256_file

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import restore_raw  # noqa: E402

DAY = "2024-01-01"


@pytest.fixture
def pinned(tmp_path):
    """One training day downloaded and pinned, as data/raw and data/manifest.json hold it."""
    raw, manifest = tmp_path / "raw", tmp_path / "manifest.json"
    download_day(DAY, raw_dir=raw, manifest=manifest, client=client(tmp_path, serve([])))
    return raw, manifest


def test_remove_then_restore_gives_back_the_pinned_bytes(tmp_path, pinned):
    raw, manifest = pinned
    before = {p.name: sha256_file(p) for p in (raw / DAY).iterdir()}
    gone = restore_raw.remove([DAY], raw, manifest)
    assert len(gone) == 2 and not (raw / DAY).exists()
    calls = []
    left = restore_raw.restore([DAY], raw, manifest, client(tmp_path, serve(calls)))
    assert left == [] and len(calls) == 2
    assert {p.name: sha256_file(p) for p in (raw / DAY).iterdir()} == before
    assert all(p.stat().st_mode & 0o222 == 0 for p in (raw / DAY).iterdir())


def test_restore_requests_only_what_is_missing(tmp_path, pinned):
    raw, manifest = pinned
    (raw / DAY / "incremental_book_L2.csv.gz").unlink()
    calls = []
    assert restore_raw.restore([DAY], raw, manifest, client(tmp_path, serve(calls))) == []
    assert len(calls) == 1 and "incremental_book_L2" in calls[0]
    calls.clear()
    assert restore_raw.restore([DAY], raw, manifest, client(tmp_path, serve(calls))) == []
    assert calls == []


def test_a_restored_file_that_differs_from_its_pin_is_not_placed(tmp_path, pinned):
    raw, manifest = pinned
    restore_raw.remove([DAY], raw, manifest)

    def changed(url):
        from test_download import FakeResponse

        return FakeResponse(BODY[url.split("/")[5]] + b"x")

    left = restore_raw.restore([DAY], raw, manifest, client(tmp_path, changed))
    assert left and "differs from the pinned" in left[0]
    assert not list((raw / DAY).glob("*.csv.gz"))


def test_remove_refuses_a_file_that_is_not_the_pinned_one_and_removes_nothing(pinned):
    raw, manifest = pinned
    book = raw / DAY / "incremental_book_L2.csv.gz"
    book.chmod(0o644)
    book.write_bytes(b"other")
    with pytest.raises(restore_raw.Refused, match="nothing removed"):
        restore_raw.remove([DAY], raw, manifest)
    assert (raw / DAY / "trades.csv.gz").exists()


def test_test_days_are_refused_before_anything_happens():
    splits = {"train": [DAY], "val": ["2025-01-01"], "test": ["2025-07-01"]}
    assert restore_raw.resolve([], splits) == [DAY, "2025-01-01"]
    assert restore_raw.resolve(["val"], splits) == ["2025-01-01"]
    for arg in ("test", "2025-07-01", "2026-10-01"):
        with pytest.raises(restore_raw.Refused):
            restore_raw.resolve([arg], splits)


def test_a_day_without_both_pins_is_refused_before_any_request(tmp_path):
    calls = []
    with pytest.raises(restore_raw.Refused, match="manifest pins"):
        restore_raw.restore([DAY], tmp_path, tmp_path / "m.json", client(tmp_path, serve(calls)))
    assert calls == []
