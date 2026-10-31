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
- Set aside: Ilia moved the folder out of the repository on 2026-10-30, to
  ~/toxic-flow-void/fb5cb1e00ce5_interrupted_2026-10-29 (451 files, no subfolders). Its
  files' SHA-256 values, computed without opening any file's contents, are in
  docs/void_run_fb5cb1e00ce5.sha256 (that list's own SHA-256:
  3446e7193007d8eceafc987abaf923ae48cc3a51f6d220f15052d9e6ac2f4a76). To check the folder
  is untouched: `cd ~/toxic-flow-void/fb5cb1e00ce5_interrupted_2026-10-29 && shasum -a 256 -c
  ~/Projects/toxic-flow/docs/void_run_fb5cb1e00ce5.sha256`.
- Restart: from the same committed config, so the same config hash and results folder
  (results/fb5cb1e00ce5), from the first cell, started at 2026-10-30T03:03:20Z on a clean
  tree. No code or config changed.
- Effect on results: none. Only the restarted run is reported.

## 5. The MDE printed from the frozen s is 0.0230 bp, section 9 says 0.0231 bp (2026-10-30)

- What: section 9 freezes "s = 0.0329 bp. MDE = 0.70 s = 0.0231 bp." scripts/analyse.py
  reads s = 0.0329 from that line, as section 9 says, and src/toxic_flow/eval/bootstrap.py
  mde() gives (z_0.975 + z_0.80) x 0.0329 / 4 = 0.023043 bp, printed as 0.0230 bp. The
  0.0231 in section 9 was worked out from s before rounding: 0.032923 bp on the training
  days (run 58c46cc49981; analysis.mde_inputs), which gives 0.023059 bp.
- Found: after results/summary.json was written (b111530), before the paper was built.
- Change: none to code, configs or PREREGISTRATION.md. The summary keeps the MDE from the
  frozen s, as the committed code computes it.
- Both results: with MDE 0.023043 bp (reported) and with 0.023059 bp (section 9's
  figure), H1 is "no detectable difference" in both, C1 and C2 pass in both (C2 threshold
  0.0691 bp and 0.0692 bp; C2 beat B1 by 2.3888 bp), C3 does not flag in both, and the C4
  statement is the same. The H1 sentence differs only in its last number: "The study could
  detect effects of 0.0230 bp or larger." against "... 0.0231 bp or larger."
- Effect on results: none on any verdict; the printed MDE is 0.0230 bp, not 0.0231 bp.

## 6. Post-hoc: the test-day spread of D and the MDE at it (Ilia, 2026-10-31)

- Ilia's decision: "add to summary.json the test-day SD of D and the MDE at that SD,
  labelled post-hoc and not part of the pre-registered analysis ... The paper states both
  numbers next to the H1 sentence, so 'could detect effects of 0.0230 bp' never stands
  alone."
- Why: the leakage audit (docs/audit_M5.md, lesser finding 1) found that D varied more on
  the test days than the s the MDE was planned with, so the planned MDE overstates what
  the test could detect.
- Change: src/toxic_flow/eval/analysis.py summary() adds posthoc_sd_bp (standard deviation
  of the primary cell's daily D, B3 minus B2b, over the 16 test days), posthoc_mde_bp
  (section 9's formula at that SD and n = 16) and posthoc_note, which labels both as
  post-hoc (test in tests/unit/test_analysis.py). results/summary.json was rebuilt with the
  same command and inputs as in b111530; every earlier key is unchanged.
- Values: posthoc_sd_bp 0.0503 bp against the planned s of 0.0329 bp; posthoc_mde_bp
  0.0352 bp against the planned MDE of 0.0230 bp. Power at 0.0230 bp with this SD is about
  45%, not 80% (computed for this entry, not a key of summary.json).
- Effect on results: adds two reported numbers; no verdict uses them and none changes. The
  pre-registered sentence of section 11 is printed as committed, with the post-hoc numbers
  beside it in the paper.
