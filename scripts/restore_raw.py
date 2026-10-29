#!/usr/bin/env python3
"""Restore the training and validation raw files, byte for byte, or remove them to free disk.

Usage: uv run python scripts/restore_raw.py [train|val|YYYY-MM-DD ...]
           fetch every pinned file that is missing (default: train and val)
       uv run python scripts/restore_raw.py --remove [train|val|YYYY-MM-DD ...]
           remove the raw files of those days, each only after it matches its pin

Ilia's decision of 2026-10-28 (docs/disk_budget.md, DEVIATIONS.md): data/raw for the 18
training and validation days may be removed, because the files are public and pinned by
SHA-256 in data/manifest.json, so they can be fetched again and checked to be the same
bytes. Test-day files are never removed and never restored here: any day outside train and
val is refused before anything is read, removed or requested.

Restoring goes through the downloader (toxic_flow.data.download.download_day), the only
code that writes data/raw: the split lock, the request limits of TardisClient, the
never-overwrite link and the check that a fetched file equals its pin all apply. A day is
restored only if both of its files are pinned; a file the manifest does not know is not
restored, since nothing would prove it is the same file.
"""

import argparse
import sys
from pathlib import Path

from toxic_flow.data.download import (
    MANIFEST,
    RAW,
    DiskSpaceError,
    ManifestError,
    download_day,
    load_manifest,
    sha256_file,
)
from toxic_flow.data.split_lock import load_splits, normalise
from toxic_flow.data.tardis import DATA_TYPES, StopRequests, TardisClient

ALLOWED = ("train", "val")


class Refused(RuntimeError):
    pass


def resolve(args: list[str], splits: dict[str, list[str]]) -> list[str]:
    """Days named by split or date, only training and validation days."""
    allowed = [d for s in ALLOWED for d in splits[s]]
    days = []
    for a in args or list(ALLOWED):
        for d in splits[a] if a in splits else [normalise(a)]:
            if d not in allowed:
                raise Refused(f"{d} is not a training or validation day")
            days.append(d)
    return days


def pins(day: str, manifest: Path) -> dict[str, dict]:
    pinned = {e["data_type"]: e for e in load_manifest(manifest) if e["date"] == day}
    if set(pinned) != set(DATA_TYPES):
        raise Refused(f"{day}: manifest pins {sorted(pinned)}, need {list(DATA_TYPES)}")
    return pinned


def problem(path: Path, pin: dict) -> str | None:
    """Why the file at path is not the pinned file, or None if it is."""
    if not path.is_file():
        return "missing"
    if path.stat().st_size != pin["bytes"]:
        return f"{path.stat().st_size} bytes, pinned {pin['bytes']}"
    if sha256_file(path) != pin["sha256"]:
        return "SHA-256 differs from the manifest"
    if path.stat().st_mode & 0o222:
        return "writable, raw files are read-only"
    return None


def restore(days: list[str], raw: Path = RAW, manifest: Path = MANIFEST, client=None) -> list[str]:
    """Fetch the missing files of each day; return what is still wrong afterwards."""
    for day in days:
        pins(day, manifest)  # every day checked before the first request
    client = client or TardisClient()  # one client, so failures and waits add up
    left = []
    for day in days:
        try:
            download_day(day, raw_dir=raw, manifest=manifest, client=client)
        except (StopRequests, DiskSpaceError, ManifestError) as e:
            left.append(f"{day}: stopped: {e}")
            break
        for t, pin in pins(day, manifest).items():
            if why := problem(raw / day / f"{t}.csv.gz", pin):
                left.append(f"{day}/{t}: {why}")
    return left


def remove(days: list[str], raw: Path = RAW, manifest: Path = MANIFEST) -> list[str]:
    """Remove each day's raw files, all of them checked against their pins first, so what
    is removed is exactly what restore() brings back. Return the files removed."""
    files = []
    for day in days:
        for t, pin in pins(day, manifest).items():
            path = raw / day / f"{t}.csv.gz"
            why = problem(path, pin)
            if why == "missing":
                continue
            if why:
                raise Refused(f"{day}/{t}: {why}; nothing removed")
            files.append(path)
    for path in files:
        path.unlink()
    for day in days:
        d = raw / day
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return files


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("days", nargs="*", help="train, val or YYYY-MM-DD (default: train and val)")
    p.add_argument("--remove", action="store_true", help="remove instead of restore")
    a = p.parse_args()
    try:
        days = resolve(a.days, load_splits())
        if a.remove:
            gone = remove(days)
            print(f"{len(days)} days: removed {len(gone)} raw files")
            return 0
        left = restore(days)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    for line in left:
        print("FAIL", line)
    print(f"{len(days)} days: {len(left)} problems")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
