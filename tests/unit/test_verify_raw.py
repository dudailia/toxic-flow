"""scripts/verify_raw.py, the re-check after moving data/raw (docs/ssd_move.md), on a
throwaway raw directory reached through a symlink."""

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_raw import problems  # noqa: E402


def make_raw(tmp_path):
    """An external raw directory with one read-only file, linked in as data/raw."""
    ext = tmp_path / "ssd" / "raw"
    (ext / "2025-01-01").mkdir(parents=True)
    f = ext / "2025-01-01" / "trades.csv.gz"
    f.write_bytes(b"abc")
    f.chmod(0o444)
    link = tmp_path / "repo" / "data" / "raw"
    link.parent.mkdir(parents=True)
    link.symlink_to(ext, target_is_directory=True)
    entry = {"path": "data/raw/2025-01-01/trades.csv.gz", "bytes": 3,
             "sha256": hashlib.sha256(b"abc").hexdigest()}  # fmt: skip
    return link, f, entry


def test_a_matching_copy_through_a_symlink_passes(tmp_path):
    link, _, entry = make_raw(tmp_path)
    assert problems(link, [entry]) == []


def test_a_changed_missing_writable_or_extra_file_fails(tmp_path):
    link, f, entry = make_raw(tmp_path)
    assert "SHA-256" in problems(link, [{**entry, "sha256": "0" * 64}])[0]
    assert "bytes" in problems(link, [{**entry, "bytes": 4}])[0]
    f.chmod(0o644)
    assert "writable" in problems(link, [entry])[0]
    f.chmod(0o444)
    (link / "2025-01-01" / "extra.csv.gz").write_bytes(b"x")
    assert "not in the manifest" in problems(link, [entry])[0]
    os.remove(link / "2025-01-01" / "extra.csv.gz")
    f.chmod(0o644)
    f.unlink()
    assert "missing" in problems(link, [entry])[0]
