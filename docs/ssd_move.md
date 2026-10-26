# Moving data/raw to an external SSD

Written 2026-10-26 for Ilia. Nothing has been moved. Every step below is Ilia's to run.

## What moves, and why only that

Only `data/raw` moves: today 36 files, 10 GB (`du -sh data/raw`), and the 16 test days
land there after the tag. It becomes a symlink to a folder on the SSD.

The rest of `data/` stays where it is:
- `data/manifest.json`, `data/recon.json`, `data/tardis_requests.jsonl` and
  `data/recon_logs/` are tracked by git. If `data/` itself were a symlink, git would see
  those files as deleted and the link as a new file.
- `data/converted` is a cache, evicted day by day, at most about 1.4 GB a day
  (docs/disk_budget.md). Conversion reads raw from the SSD and writes the cache to the
  internal disk; its guard (`MIN_FREE_TO_CONVERT`, 12 GB in data/convert.py) measures the
  disk of `data/converted`, so it keeps working as before.
- `data/events` is small (189 MB) and gitignored.

What the code does through the link, checked on 2026-10-26:
- The downloader and the converter open `data/raw/<date>/<type>.csv.gz` as a path, so a
  symlinked `data/raw` is transparent. The downloader's free-space check
  (`shutil.disk_usage` on the day folder) then measures the SSD, which is the disk it
  writes to.
- If the SSD is not mounted, `data/raw` is a dangling link. The downloader creates the day
  folder before it sends any request, and that fails with FileExistsError, so no request
  is sent. The converter stops with ManifestError (raw file missing). Nothing writes a raw
  file anywhere else.
- `.gitignore` says `data/raw` without a trailing slash (changed 2026-10-26). The old
  `data/raw/` matched only a directory, so git listed a symlinked `data/raw` as untracked
  and every run would have refused to start on a dirty tree.
- The M0 check AC0.5 (no test-day path under `data/`) now walks `data/` with
  `os.walk(..., followlinks=True)`. Before 2026-10-26 it used `Path.rglob`, which in
  Python 3.12 does not enter a symlinked folder, so after the move it would have passed
  without looking at any raw file.

## The disk

Format it APFS (Disk Utility, "APFS"). The raw files are read-only (mode 444) and
`tests/unit/test_raw_hashes.py` and `scripts/verify_raw.py` both fail on a writable raw
file. exFAT and FAT32 do not keep Unix permissions, so the files would read as writable.
Below the volume is called `TFSSD`; use whatever name it has under `/Volumes`.

## Steps

Before starting: no `make data`, `make run` or conversion running (`pgrep -fl toxic_flow`
prints nothing), and `git status` is clean.

1. Baseline: every raw file matches the manifest where it is now.

       uv run python scripts/verify_raw.py

   Expect `0 problems over 36 manifest entries` (2026-10-26: 0 problems, 13 s).

2. Copy to the SSD. `ditto` keeps modes and timestamps.

       mkdir -p /Volumes/TFSSD/toxic-flow
       ditto data/raw /Volumes/TFSSD/toxic-flow/raw

3. Verify the copy before switching:

       uv run python scripts/verify_raw.py --raw /Volumes/TFSSD/toxic-flow/raw

   Any FAIL line: stop, nothing has changed yet.

4. Switch. The internal copy is renamed out of the repo, not deleted: it is on the same
   disk, so the rename is instant and frees nothing yet.

       mv data/raw ~/toxic-flow-raw-internal
       ln -s /Volumes/TFSSD/toxic-flow/raw data/raw

5. Verify through the link, then the repo's own checks:

       uv run python scripts/verify_raw.py
       uv run pytest tests/unit/test_raw_hashes.py -m slow -q
       uv run python scripts/check_milestone.py M0
       git status --short

   The first line of verify_raw.py prints `data/raw -> /Volumes/TFSSD/toxic-flow/raw`.
   `git status` prints nothing.

6. The internal copy. Ilia's rule is that raw files are never deleted, so this step is
   his decision alone: once step 5 passes, `~/toxic-flow-raw-internal` is a second copy of
   files the SSD now holds and the manifest pins, and removing it frees about 10 GB on
   the internal disk. Until then it stays.

## Undo

Before step 6, the move can be undone exactly: remove the link (it holds no data) and
rename the internal copy back.

    unlink data/raw
    mv ~/toxic-flow-raw-internal data/raw
    uv run python scripts/verify_raw.py

## Day to day

- Mount the SSD before any `make data`, conversion or run. Without it, those steps stop as
  described above.
- After the tag, `make data DAYS=test` writes the test days onto the SSD through the link.
  Run `uv run python scripts/verify_raw.py` after the download as well; it re-hashes the
  new files against the hashes the downloader pinned.
- The disk watchdog in the session scratchpad watches `/`, the internal disk, where swap,
  the conversion cache and results live. The SSD's free space is checked by the
  downloader itself before each file.
