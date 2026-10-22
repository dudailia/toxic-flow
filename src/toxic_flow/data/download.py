"""Downloader: the only code that writes data/raw, and it never overwrites a file there.

Usage: uv run python -m toxic_flow.data.download train|val|test|YYYY-MM-DD

Each file lands at data/raw/<date>/<data_type>.csv.gz, read-only, with its SHA-256 pinned in
data/manifest.json. On a re-run an existing file is re-hashed against the manifest instead
of being fetched again. The split lock runs before any URL is opened.
"""

import hashlib
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from toxic_flow.data.split_lock import SplitLockError, assert_allowed, load_splits, normalise
from toxic_flow.data.tardis import DATA_TYPES, dataset_url

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"
USER_AGENT = "toxic-flow-download/0.1 (+https://github.com/dudailia/toxic-flow)"
CHUNK = 1 << 20


class ManifestError(RuntimeError):
    pass


def resolve_days(arg: str) -> list[str]:
    splits = load_splits()
    return splits[arg] if arg in splits else [normalise(arg)]


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=60)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text())["files"] if path.exists() else []


def save_manifest(path: Path, entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda e: (e["date"], e["data_type"]))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"files": entries}, indent=2) + "\n")
    os.replace(tmp, path)


def _stream(url: str, part: Path, fetch) -> tuple[int, str]:
    """Write url to part. Return (bytes, sha256). Raise OSError on a short or corrupt transfer."""
    sha, md5, n = hashlib.sha256(), hashlib.md5(), 0
    with fetch(url) as r, open(part, "wb") as f:
        expected = int(r.headers["Content-Length"])
        tardis_md5 = (r.headers.get("x-md5") or "").strip('"')
        while chunk := r.read(CHUNK):
            f.write(chunk)
            sha.update(chunk)
            md5.update(chunk)
            n += len(chunk)
    if n != expected:
        raise OSError(f"{url}: got {n} bytes, Content-Length said {expected}")
    if tardis_md5 and md5.hexdigest() != tardis_md5:
        raise OSError(f"{url}: md5 {md5.hexdigest()} does not match x-md5 {tardis_md5}")
    return n, sha.hexdigest()


def download_day(day: str, raw_dir: Path = RAW, manifest: Path = MANIFEST, fetch=_fetch):
    split = assert_allowed(day)  # first, so a refused day never reaches the network
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
        url = dataset_url(day, data_type)
        try:
            n, sha = _stream(url, part, fetch)
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
            os.link(part, dest)  # unlike rename, link fails if dest exists: never overwrite
        finally:
            part.unlink(missing_ok=True)
        dest.chmod(0o444)
        out.append(entry)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    for day in resolve_days(argv[0]):
        try:
            entries = download_day(day)
        except SplitLockError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        for e in entries:
            print(f"{e['date']} {e['data_type']}: {e['bytes']} bytes sha256 {e['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
