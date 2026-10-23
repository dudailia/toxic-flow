"""Downloader: the only code that writes data/raw, and it never overwrites a file there.

Usage: uv run python -m toxic_flow.data.download train|val|test|YYYY-MM-DD

Each file lands at data/raw/<date>/<data_type>.csv.gz, read-only, with its SHA-256 pinned in
data/manifest.json. On a re-run an existing file is re-hashed against the manifest instead
of being fetched again. The split lock runs before any URL is opened. Requests go one at a
time through TardisClient (toxic_flow.data.tardis): Retry-After is honoured, a failed file
is not retried in the same run, and the run stops at the third failure.
"""

import hashlib
import http.client
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from toxic_flow.data.split_lock import SplitLockError, assert_allowed, load_splits, normalise
from toxic_flow.data.tardis import (
    DATA_TYPES,
    RequestFailed,
    StopRequests,
    TardisClient,
    dataset_url,
)

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"
CHUNK = 1 << 20
DISK_MARGIN = 1 << 30  # keep 1 GiB free beyond the file, for the .part and conversion


class ManifestError(RuntimeError):
    pass


class DiskSpaceError(RuntimeError):
    """Not enough local disk. A local problem, so it is not counted as a request failure."""


def resolve_days(arg: str) -> list[str]:
    splits = load_splits()
    return splits[arg] if arg in splits else [normalise(arg)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text())["files"] if path.exists() else []


def save_manifest(path: Path, entries: list[dict]) -> None:
    """Write the raw entries; any other key (the converter's "converted" record) is kept."""
    entries = sorted(entries, key=lambda e: (e["date"], e["data_type"]))
    doc = json.loads(path.read_text()) if path.exists() else {}
    doc["files"] = entries
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    os.replace(tmp, path)


def _stream(url: str, part: Path, client: TardisClient) -> tuple[int, str]:
    """Write url to part. Return (bytes, sha256).

    Only the server's side counts as a request failure: missing headers, a read that fails,
    a short or corrupt transfer. A local write error propagates as it is.
    """
    sha, md5, n = hashlib.sha256(), hashlib.md5(), 0
    with client.open(url) as r:
        try:
            expected = int(r.headers["Content-Length"])
        except (KeyError, TypeError, ValueError) as e:
            client.failed(f"{url}: no usable Content-Length ({e!r})", url=url)
        tardis_md5 = (r.headers.get("x-md5") or "").strip('"')
        free = shutil.disk_usage(part.parent).free
        if free < expected + DISK_MARGIN:
            raise DiskSpaceError(f"{url} needs {expected} bytes plus 1 GiB; {free} free")
        with open(part, "wb") as f:
            while True:
                try:
                    chunk = r.read(CHUNK)
                except (OSError, http.client.HTTPException) as e:
                    client.failed(f"transfer of {url} failed: {e!r}", url=url)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                md5.update(chunk)
                n += len(chunk)
    if n != expected:
        client.failed(f"{url}: got {n} bytes, Content-Length said {expected}", url=url)
    if tardis_md5 and md5.hexdigest() != tardis_md5:
        client.failed(f"{url}: md5 {md5.hexdigest()} does not match x-md5 {tardis_md5}", url=url)
    return n, sha.hexdigest()


def download_day(
    day: str, raw_dir: Path = RAW, manifest: Path = MANIFEST, fetch=None, client=None
) -> list[dict]:
    """Download one day's files; return the manifest entries of the files now on disk.

    A file whose request fails is skipped and counted by the client; the run goes on to
    the next file. StopRequests ends the run.
    """
    split = assert_allowed(day)  # first, so a refused day never reaches the network
    client = client or (TardisClient(fetch=fetch) if fetch else TardisClient())
    day = normalise(day)
    entries = load_manifest(manifest)
    known = {(e["date"], e["data_type"]): e for e in entries}
    out = []
    for data_type in DATA_TYPES:
        dest = raw_dir / day / f"{data_type}.csv.gz"
        pinned = known.get((day, data_type))
        if dest.exists():
            if pinned is None:
                raise ManifestError(f"{dest} exists but data/manifest.json has no entry for it")
            if sha256_file(dest) != pinned["sha256"]:
                raise ManifestError(f"{dest} no longer matches its pinned SHA-256")
            out.append(pinned)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        part.unlink(missing_ok=True)  # a hard kill can leave one, read-only
        url = dataset_url(day, data_type)
        try:
            n, sha = _stream(url, part, client)
            if pinned is not None and sha != pinned["sha256"]:
                # A file evicted from disk may be fetched again, but only if it is identical.
                raise ManifestError(f"{url} now differs from the pinned SHA-256")
            entry = pinned or {
                "date": day,
                "data_type": data_type,
                "split": split,
                "url": url,
                "path": f"data/raw/{day}/{data_type}.csv.gz",
                "bytes": n,
                "sha256": sha,
                "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            if pinned is None:
                # Pin before placing the file. A crash in between then leaves an entry with
                # no file, which the next run re-fetches and verifies; the other order would
                # leave an unpinned file that blocks every later run.
                entries.append(entry)
                save_manifest(manifest, entries)
            # Read-only before it is placed, so no crash can leave a writable raw file.
            part.chmod(0o444)
            os.link(part, dest)  # unlike rename, link fails if dest exists: never overwrite
        except RequestFailed as e:
            print(f"failed, not retried in this run: {e}", file=sys.stderr)
            continue
        finally:
            part.unlink(missing_ok=True)
        out.append(entry)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    client = TardisClient()  # one client for the run, so failures and waits add up
    for day in resolve_days(argv[0]):
        try:
            entries = download_day(day, client=client)
        except SplitLockError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        except (StopRequests, DiskSpaceError) as e:
            print(f"stopped: {e}", file=sys.stderr)
            return 1
        for e in entries:
            print(f"{e['date']} {e['data_type']}: {e['bytes']} bytes sha256 {e['sha256'][:12]}")
    if client.failures:
        print(f"{client.failures} request(s) failed; re-run later to fetch them", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
