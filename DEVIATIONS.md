# DEVIATIONS

First entry, written by Ilia right after pushing the tag: tag name, commit hash, and the
push time shown on GitHub.

Each later entry: date, what changed, why, which results it affects, fixing commit.

## 1. The tag (2026-10-29)

- Tag: prereg-v1, annotated, tag object 422f3b4ffcc1d3665d58d209855d595bf50f3814, on commit
  66c639d83396cb58e8236beb76a715f8ac56ffdf. `git ls-remote --tags origin` lists the same
  tag object.
- Created: 2026-10-29T02:38:54Z, the tagger date that the GitHub API returns for the tag object
  (`gh api repos/dudailia/toxic-flow/git/tags/422f3b4...`).
- Pushed: between 2026-10-29T02:38:54Z (created) and 2026-10-29T02:40:37Z (`git ls-remote`
  listed it on origin, in this session's log). The GitHub API gives no exact push time for
  it: the repository activity endpoint lists branch pushes only (none for refs/tags), and the
  events feed, queried at 2026-10-29T02:49Z, had no event newer than 2026-10-27. Written by
  Claude at Ilia's request (overnight plan, item 2), not by Ilia as planned above.
- Commits after the tag, before any test-day file: bb9f551 (scripts/site_replay.py says
  which raw day it needs; the project page's data, not used by M5), and the commits of
  entries 2 and 3 below. None changes PREREGISTRATION.md, configs/ or code under src/.

## 2. A raw training file was missing (found 2026-10-28)

- What: data/raw/2024-05-01/incremental_book_L2.csv.gz (941,657,804 bytes, pinned in
  data/manifest.json) was not on disk. scripts/verify_raw.py found it missing; it had
  passed on 2026-10-26 at 11:56 (0 problems over 36 files).
- Cause: removed by hand through macOS System Settings > Storage, not by any code. The
  folder's last change was 2026-10-26 23:00:54 EDT. The macOS log for that time: System
  Settings opened at 22:58:07, its Storage pane ran from 22:58:53 to 23:02:32, two mouse
  clicks at 23:00:52.8 and 23:00:53.8, and storagekitd measured the volume again at
  23:00:55. No Claude session on this machine ran a command at that time (all transcripts
  searched), no download of that day ran after 2026-10-23 (data/tardis_requests.jsonl),
  and no code in the repository deletes or moves a raw file. It was the largest file in
  data/raw, so it was first on that pane's list of large files.
- Guard: tests/unit/test_raw_guard.py pins every call in src/, scripts/ and paper/ that can
  delete or move a file, each with the reason it cannot reach data/raw; a new one fails the
  test (checked by planting one). No code had to change.
- Fix: scripts/restore_raw.py fetched it again through the downloader on 2026-10-29
  (request logged in data/tardis_requests.jsonl). Its SHA-256 equals the pin, so it is the
  same file.
- Effect on results: none. The file was missing from 2026-10-26 23:00 EDT to 2026-10-29.
  The last run in results/ started at 2026-10-26T21:15:55Z (fb21705e1269, validation days),
  before it was removed, so every committed result that used 2024-05-01 read the pinned
  bytes. Nothing read the file while it was missing.

## 3. Training and validation raw files removed to free disk (Ilia, 2026-10-28)

- Ilia's decision: "I approve removing data/raw for the 18 train and val days only, after
  scripts/restore_raw.py has been tested, because they are public and pinned by SHA-256.
  Record it in docs/disk_budget.md and DEVIATIONS.md. Never touch test-day files."
- This changes the rule that data/raw is never deleted, for these 36 files only. Test-day
  files are never removed. The manifest keeps every pin.
- Tested first: tests/unit/test_restore_raw.py (remove then restore gives back the pinned
  bytes; only missing files are requested; a fetched file that differs from its pin is not
  placed; test days are refused before anything is read or requested), and the live restore
  in entry 2.
- To restore: `uv run python scripts/restore_raw.py` (all 18 days) or with a date; then
  `uv run python scripts/verify_raw.py`. Needed before re-running anything on a training or
  validation day, `make site-data`, the slow test test_raw_hashes.py, or the M0 and M1
  checks that read raw files.
- Effect on results: none. The confirmatory run reads test days only; every training and
  validation result is already in results/ and the files can be fetched again as the same
  bytes.

## 4. The first confirmatory run was cut off by a reboot (2026-10-29)

- What: the confirmatory run (configs/runs/confirmatory.yaml, committed in 255b523, results
  folder results/fb5cb1e00ce5) started at about 07:47Z on 2026-10-29 through
  tests/canary/run_c2.py. The Mac restarted for a macOS update: Ilia gives about 05:49 EDT;
  the run's folder was last written at 06:01:01 EDT; the machine was up again at 08:47:22
  EDT (kern.boottime). The run never finished: it wrote no metrics.parquet and no
  meta.json, so it has no result.
- Treated as void, on Ilia's instruction, before any of its results were analysed: none of
  its files was opened, read, analysed or committed.
- Restart: from the same committed config, so the same config hash and results folder
  (results/fb5cb1e00ce5), from the first cell. No code or config changed.
- Effect on results: none. Only the restarted run is reported.
