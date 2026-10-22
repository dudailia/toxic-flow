import gzip
import hashlib
import io
import json
from datetime import datetime

import pytest

from toxic_flow.data.download import ManifestError, download_day, resolve_days
from toxic_flow.data.tardis import StopRequests, TardisClient

BODY = {
    "incremental_book_L2": gzip.compress(b"exchange,symbol\nbinance-futures,BTCUSDT\n"),
    "trades": gzip.compress(b"exchange,symbol\n"),
}


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body)), **(headers or {})}


def client(tmp_path, fetch, slept=None, clock=None):
    """A client whose waits are recorded instead of slept, with its own state file."""
    slept = [] if slept is None else slept
    return TardisClient(
        fetch=fetch,
        state=tmp_path / "tardis_wait.json",
        sleep=slept.append,
        clock=clock or (lambda: 1_000_000.0 + sum(slept)),
    )


def http_error(url, code, retry_after=None):
    import urllib.error

    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError(url, code, "error", headers, None)


def serve(calls):
    def fetch(url):
        calls.append(url)
        data_type = url.split("/")[5]
        return FakeResponse(BODY[data_type])

    return fetch


def test_manifest_entry_fields(tmp_path):
    calls = []
    manifest = tmp_path / "manifest.json"
    entries = download_day(
        "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve(calls))
    )
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
    download_day(
        "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve([]))
    )
    path = tmp_path / "2024-01-01" / "trades.csv.gz"
    before = path.stat().st_mtime_ns
    calls = []
    download_day(
        "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve(calls))
    )
    assert calls == []
    assert path.stat().st_mtime_ns == before


def test_hash_mismatch_raises(tmp_path):
    manifest = tmp_path / "manifest.json"
    download_day(
        "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve([]))
    )
    path = tmp_path / "2024-01-01" / "trades.csv.gz"
    path.chmod(0o644)
    path.write_bytes(b"tampered")
    with pytest.raises(ManifestError):
        download_day(
            "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve([]))
        )


def test_file_without_manifest_entry_raises(tmp_path):
    (tmp_path / "2024-01-01").mkdir()
    (tmp_path / "2024-01-01" / "trades.csv.gz").write_bytes(b"unknown origin")
    with pytest.raises(ManifestError):
        download_day(
            "2024-01-01",
            raw_dir=tmp_path,
            manifest=tmp_path / "m.json",
            client=client(tmp_path, serve([])),
        )


def test_short_transfer_is_a_failure_and_leaves_no_file(tmp_path):
    def fetch(url):
        return FakeResponse(b"abc", headers={"Content-Length": "10"})

    c = client(tmp_path, fetch)
    entries = download_day("2024-01-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", client=c)
    assert entries == []
    assert c.failures == 2
    assert not [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "tardis_wait.json"]


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
        download_day(
            "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve([]))
        )
    monkeypatch.setattr(dl, "save_manifest", real_save)
    entries = download_day(
        "2024-01-01", raw_dir=tmp_path, manifest=manifest, client=client(tmp_path, serve([]))
    )
    assert [e["data_type"] for e in entries] == ["incremental_book_L2", "trades"]


def test_retry_after_is_honoured_and_the_url_not_retried(tmp_path):
    calls, slept = [], []

    def fetch(url):
        calls.append(url)
        if "incremental_book_L2" in url:
            raise http_error(url, 429, retry_after=7)
        return FakeResponse(BODY["trades"])

    c = client(tmp_path, fetch, slept)
    entries = download_day("2024-01-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", client=c)
    assert [e["data_type"] for e in entries] == ["trades"]
    assert len(calls) == 2 and calls[0] != calls[1]  # each URL once, no retry
    assert slept == [7]  # the next request waited out Retry-After
    assert c.failures == 1


def test_stops_after_three_failures(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        raise TimeoutError("timed out")

    c = client(tmp_path, fetch)
    download_day("2024-01-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", client=c)
    with pytest.raises(StopRequests):
        download_day("2024-02-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", client=c)
    assert len(calls) == 3


def test_long_retry_after_stops_the_run_and_is_remembered(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        raise http_error(url, 429, retry_after=79529)

    with pytest.raises(StopRequests):
        download_day(
            "2024-01-01",
            raw_dir=tmp_path,
            manifest=tmp_path / "m.json",
            client=client(tmp_path, fetch),
        )
    assert len(calls) == 1
    # A new run before the wait is over makes no request at all.
    with pytest.raises(StopRequests):
        download_day(
            "2024-01-01",
            raw_dir=tmp_path,
            manifest=tmp_path / "m.json",
            client=client(tmp_path, fetch),
        )
    assert len(calls) == 1
