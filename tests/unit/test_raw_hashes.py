"""AC1.2: every raw file on disk matches its pinned SHA-256 and size, is read-only, and no
raw file lacks a manifest entry. Slow: it reads every byte of data/raw."""

from pathlib import Path

import pytest

from toxic_flow.data.download import MANIFEST, RAW, load_manifest, sha256_file

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_ac1_2_every_raw_file_matches_its_pinned_sha256():
    entries = load_manifest(MANIFEST)
    assert entries, "data/manifest.json is empty"
    for e in entries:
        path = ROOT / e["path"]
        assert path.exists(), f"{path} is pinned but missing"
        assert path.stat().st_size == e["bytes"], path
        assert sha256_file(path) == e["sha256"], path
        assert path.stat().st_mode & 0o222 == 0, f"{path} is writable"


def test_no_raw_file_without_a_manifest_entry():
    pinned = {ROOT / e["path"] for e in load_manifest(MANIFEST)}
    on_disk = {p for p in RAW.rglob("*") if p.is_file()} if RAW.exists() else set()
    assert on_disk <= pinned, sorted(on_disk - pinned)[:5]
