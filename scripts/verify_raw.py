#!/usr/bin/env python3
"""Re-verify every raw file against data/manifest.json, for example after moving data/raw
to an external disk (docs/ssd_move.md).

Usage: uv run python scripts/verify_raw.py                 data/raw, through any symlink
       uv run python scripts/verify_raw.py --raw /Volumes/X/toxic-flow/raw
           a copy that is not yet linked in, to check it before the switch

For each manifest entry it checks that the file exists under the raw directory, has the
pinned size and SHA-256, and is read-only; and that the directory holds no file without
an entry. It reads files and writes nothing. Exit 0 only if every check passes. It reads
every byte: the 36 training and validation files (10 GB) took 13 s on the internal disk on
2026-10-26; a USB disk is slower.
"""

import argparse
import os
import sys
from pathlib import Path

from toxic_flow.data.download import MANIFEST, RAW, load_manifest, sha256_file


def problems(raw: Path, entries: list[dict]) -> list[str]:
    """Every way the files under raw differ from the manifest entries; empty if none."""
    out, pinned = [], set()
    for e in entries:
        # Entries name data/raw/<date>/<type>.csv.gz; the same relative path under raw.
        rel = Path(e["path"]).relative_to("data/raw")
        path = raw / rel
        pinned.add(rel)
        if not path.is_file():
            out.append(f"{rel}: missing")
        elif path.stat().st_size != e["bytes"]:
            out.append(f"{rel}: {path.stat().st_size} bytes, pinned {e['bytes']}")
        elif sha256_file(path) != e["sha256"]:
            out.append(f"{rel}: SHA-256 differs from the manifest")
        elif path.stat().st_mode & 0o222:
            out.append(f"{rel}: writable, raw files are read-only")
    # os.walk follows the link at raw itself; nothing under it should be a link.
    for parent, _, files in os.walk(raw):
        for f in files:
            rel = (Path(parent) / f).relative_to(raw)
            if rel not in pinned:
                out.append(f"{rel}: on disk but not in the manifest")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--raw", type=Path, default=RAW, help="raw directory (default data/raw)")
    a = p.parse_args()
    entries = load_manifest(MANIFEST)
    print(f"{a.raw} -> {a.raw.resolve()}: {len(entries)} manifest entries")
    found = problems(a.raw, entries)
    for line in found:
        print("FAIL", line)
    print(f"{len(found)} problems over {len(entries)} manifest entries")
    return 1 if found or not entries else 0


if __name__ == "__main__":
    sys.exit(main())
