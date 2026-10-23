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
