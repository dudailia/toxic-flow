import gzip
import hashlib
import io
import json
from datetime import datetime

import pytest

from toxic_flow.data.download import ManifestError, download_day, resolve_days

BODY = {
    "incremental_book_L2": gzip.compress(b"exchange,symbol\nbinance-futures,BTCUSDT\n"),
    "trades": gzip.compress(b"exchange,symbol\n"),
}


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body)), **(headers or {})}


def serve(calls):
    def fetch(url):
        calls.append(url)
        data_type = url.split("/")[5]
        return FakeResponse(BODY[data_type])

    return fetch


def test_manifest_entry_fields(tmp_path):
    calls = []
    manifest = tmp_path / "manifest.json"
    entries = download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve(calls))
    assert len(calls) == 2
    book = next(e for e in entries if e["data_type"] == "incremental_book_L2")
    body = BODY["incremental_book_L2"]
    assert book["sha256"] == hashlib.sha256(body).hexdigest()
    assert book["bytes"] == len(body)
    assert book["split"] == "train"
    assert book["date"] == "2024-01-01"
    assert book["url"].endswith("/incremental_book_L2/2024/01/01/BTCUSDT.csv.gz")
    assert datetime.fromisoformat(book["downloaded_at"]).utcoffset().total_seconds() == 0
    assert (tmp_path / "2024-01-01" / "incremental_book_L2.csv.gz").read_bytes() == body
    assert json.loads(manifest.read_text())["files"] == entries
    assert not list(tmp_path.rglob("*.part"))


def test_existing_file_not_rewritten(tmp_path):
    manifest = tmp_path / "manifest.json"
    download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve([]))
    path = tmp_path / "2024-01-01" / "trades.csv.gz"
    before = path.stat().st_mtime_ns
    calls = []
    download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve(calls))
    assert calls == []
    assert path.stat().st_mtime_ns == before


def test_hash_mismatch_raises(tmp_path):
    manifest = tmp_path / "manifest.json"
    download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve([]))
    path = tmp_path / "2024-01-01" / "trades.csv.gz"
    path.chmod(0o644)
    path.write_bytes(b"tampered")
    with pytest.raises(ManifestError):
        download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve([]))


def test_file_without_manifest_entry_raises(tmp_path):
    (tmp_path / "2024-01-01").mkdir()
    (tmp_path / "2024-01-01" / "trades.csv.gz").write_bytes(b"unknown origin")
    with pytest.raises(ManifestError):
        download_day("2024-01-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", fetch=serve([]))


def test_short_transfer_raises_and_leaves_no_file(tmp_path):
    def fetch(url):
        return FakeResponse(b"abc", headers={"Content-Length": "10"})

    with pytest.raises(OSError):
        download_day("2024-01-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", fetch=fetch)
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_resolve_days():
    assert resolve_days("train")[0] == "2024-01-01"
    assert len(resolve_days("val")) == 6
    assert resolve_days("2024-01-01") == ["2024-01-01"]


def test_crash_before_manifest_save_recovers(tmp_path, monkeypatch):
    # A crash between placing a raw file and pinning it must not leave a file that
    # blocks every later run.
    import toxic_flow.data.download as dl

    real_save = dl.save_manifest
    crashed = []

    def crash_once(path, entries):
        if not crashed:
            crashed.append(True)
            raise KeyboardInterrupt
        real_save(path, entries)

    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(dl, "save_manifest", crash_once)
    with pytest.raises(KeyboardInterrupt):
        download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve([]))
    monkeypatch.setattr(dl, "save_manifest", real_save)
    entries = download_day("2024-01-01", raw_dir=tmp_path, manifest=manifest, fetch=serve([]))
    assert [e["data_type"] for e in entries] == ["incremental_book_L2", "trades"]
