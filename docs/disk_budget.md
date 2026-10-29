# Disk and memory budget (measured 2026-10-23, after the disk filled and the Mac rebooted)

Decimal GB (10^9 bytes), as df -H prints. Measured values come from data/manifest.json
(raw bytes), data/converted/2024-01-01/convert.json (the one day converted on disk), the
in-memory conversion records of 2024-06-01 and 2025-01-01, and /usr/bin/time on those
runs. Estimates say so and give their basis.

## Raw bytes per day (measured, both files)

| Day | Raw GB |
|---|---|
| 2024-01-01 | 0.567 |
| 2024-02-01 | 0.573 |
| 2024-03-01 | 0.738 |
| 2024-04-01 | 0.739 |
| 2024-05-01 | 1.010 |
| 2024-06-01 | 0.259 |
| 2024-07-01 | 0.493 |
| 2024-08-01 | 0.855 |
| 2024-09-01 | 0.581 |
| 2024-10-01 | 0.727 |
| 2024-11-01 | 0.716 |
| 2024-12-01 | 0.474 |
| 2025-01-01 | 0.428 |
| 2025-02-01 | 0.441 |
| 2025-03-01 | 0.669 |
| 2025-04-01 | 0.786 |
| 2025-05-01 | 0.573 |
| 2025-06-01 | 0.475 |

18 days: 11.11 GB. Smallest 0.259 GB, largest 1.010 GB, mean 0.617 GB.

## One conversion

- Converted bytes, measured on 2024-01-01: 0.776 GB for 0.567 GB
  raw, a ratio of 1.368. The other days are estimates at the same ratio: events per
  raw byte were 0.1765 (2024-01-01), 0.1735 (2024-06-01) and
  0.1799 (2025-01-01). Largest day, 2024-05-01: about 1.38 GB.
- Peak memory, measured: 7.55 GB for the on-disk conversion of 2024-01-01
  (100.1M events, 153 s); 5.83 GB and 5.15 GB for the
  in-memory conversions of 2024-01-01 and 2024-06-01 (45.0M events). Estimate for 2024-05-01, if
  memory scales with events: about 13.4 GB, near the machine's 16 GB.
- Temporary disk, measured: the parts are written once into a staging directory and renamed,
  so files need no more than the converted size. The larger cost is swap: macOS keeps it on
  the same disk, and one in-memory conversion of 2024-12-01 took free disk from 2.1 GB to
  0.66 GB as swap grew from 10.4 to 12.1 GB. Swap growth is not bounded by the job, which is
  how the disk filled.

## Totals

- Raw, 18 train and val days: 11.11 GB (measured, on disk).
- Converted, 18 days all at once: about 15.2 GB (estimate); as a cache, one day at
  a time: at most about 1.38 GB.
- Raw, 16 test days: unknown, since their files cannot be requested before the tag. At the
  18-day mean, about 9.9 GB; between 4.2 GB (all like the smallest day) and
  16.2 GB (all like the largest).
- Raw, all 34 days: about 21.0 GB (15.3 to 27.3 GB).
- Converted, all 34 at once: about 28.7 GB (estimate); never needed with the cache.

## Against the rules of 2026-10-23

- Free disk now: 13.4 GB.
- Rule 3, no conversion below 15 GB free: not met, 1.6 GB short. With
  the largest converted day on top, about 16.4 GB are needed to work through M1 and M2.
- Rule 4, raw for all 34 days with 30 GB to spare: the 16 test days need about 9.9 GB
  more, so free disk must be about 39.9 GB now (34.2 to 46.2 GB).
  It is 13.4 GB: short by about 26.4 GB (20.7 to 32.7 GB).

Verdict: the raw data for all 34 days will not fit with 30 GB to spare, so work stops here
for an external SSD or a cloud machine, as Ilia asked. No raw file was deleted.

## Rules as revised by Ilia, 2026-10-23 (later the same evening)

- Rule 4 applies at M5, not now. The test days are downloaded only after the tag, and an
  external SSD or a cloud machine will be added before then. Until M5 the budget is the 18
  train and val days, already on disk.
- Conversion floor: 12 GB free (was 15 GB). If free disk falls below 12 GB at any point,
  work stops and is reported.
- Memory guard: before each conversion, peak memory is estimated from the day's events at
  7.55 GB per 100M events (2024-01-01). Events are not known before converting, so they
  are the raw rows (trades plus book) times 1.0166, the 2024-01-01 ratio of events to rows.
  A day above 11 GB, or above the memory free at that moment (free, inactive and
  speculative pages), is skipped and flagged rather than allowed to swap. Days run from
  smallest to largest.

| Day | Raw rows (M, counted) | Estimated peak (GB) |
|---|---|---|
| 2024-06-01 | 44.7 | 3.4 |
| 2025-01-01 | 75.9 | 5.8 |
| 2025-02-01 | 78.6 | 6.0 |
| 2024-12-01 | 83.4 | 6.4 |
| 2025-06-01 | 84.5 | 6.5 |
| 2024-07-01 | 86.7 | 6.7 |
| 2024-01-01 | 98.5 | 7.6 |
| 2024-02-01 | 99.6 | 7.6 |
| 2024-09-01 | 102.5 | 7.9 |
| 2025-05-01 | 103.8 | 8.0 |
| 2025-03-01 | 120.9 | 9.3 |
| 2024-11-01 | 127.8 | 9.8 |
| 2024-10-01 | 129.0 | 9.9 |
| 2024-03-01 | 132.0 | 10.1 |
| 2024-04-01 | 133.9 | 10.3 |
| 2025-04-01 | 142.1 | 10.9 |
| 2024-08-01 | 157.3 | 12.1 |
| 2024-05-01 | 184.6 | 14.2 |

Two days are over 11 GB: 2024-08-01 and 2024-05-01, both training days. Splitting them
differently would not help much: the reader holds the whole day's book rows (34 bytes each,
6.3 GB for 2024-05-01) before cutting parts. A two-pass reader that keeps only timestamps
for the cut search would lower it; it is not built. hftbacktest itself takes a day as
several files, so the limit is this reader, not the engine.

## Training and validation raw files removed (Ilia's decision, 2026-10-28)

Ilia: "I approve removing data/raw for the 18 train and val days only, after
scripts/restore_raw.py has been tested, because they are public and pinned by SHA-256."
Recorded in DEVIATIONS.md, entry 3.

- Tested first: tests/unit/test_restore_raw.py, and a live restore on 2026-10-29 of
  2024-05-01's book file, which had been removed by hand (DEVIATIONS.md, entry 2): fetched
  through the downloader in 70 s, SHA-256 equal to its pin.
- Removed on 2026-10-29 with `uv run python scripts/restore_raw.py --remove train val`: 36
  files, each checked against its pin first. data/raw held 11.12 GB before (du); free disk
  went from 18.00 GB to 29.13 GB (df). No test-day file existed or was touched.
- The manifest keeps all 36 pins. `uv run python scripts/verify_raw.py` now reports the 36
  files missing; that is expected until they are restored.
- To bring them back: `uv run python scripts/restore_raw.py` (all 18 days, about 11.1 GB)
  or with one date, then `uv run python scripts/verify_raw.py`. Needed before any run on a
  training or validation day, `make site-data` (it replays 2024-06-01), the slow test
  tests/unit/test_raw_hashes.py, and the M0 and M1 checks that read raw files.
- For M5: the 16 test days need about 9.9 GB of raw (4.2 to 16.2 GB, section "Totals"), so
  about 19.2 GB stays free after the download (13.0 to 24.9 GB), above the 12 GB conversion
  floor, with one converted day (at most about 1.4 GB) cached at a time.
