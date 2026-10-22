# Data recon (M0)

What the data source and the venue look like before anything is designed around them.
Machine-readable record: data/recon.json (written by scripts/recon.py on 2026-10-22,
15:26 to 15:37 UTC). Benchmark record: data/benchmark_m0.json.

## Source

- Tardis.dev free first-day-of-month files, exchange `binance-futures`, symbol `BTCUSDT`,
  data types `incremental_book_L2` and `trades`, URL form
  `https://datasets.tardis.dev/v1/binance-futures/<type>/<yyyy>/<mm>/<dd>/BTCUSDT.csv.gz`.
- Tardis exchange API (`https://api.tardis.dev/v1/exchanges/binance-futures`), as recorded in
  `exchange_meta`: BTCUSDT perpetual available since 2019-11-17, datasets exported up to
  2026-10-22, with data types trades, incremental_book_L2, quotes, book_snapshot_5,
  book_snapshot_25, derivative_ticker, liquidations and book_ticker. Recorder in GCP
  asia-northeast1 (Tokyo); the exchange is listed as AWS ap-northeast-1 (Tokyo). Book data
  comes from the `depth` stream subscribed at `depth@0ms`; Tardis adds the start-of-day
  snapshot from the REST API (top 1000 levels) and restarts the connection when the `pu`/`u`
  sequence numbers show a gap.
- Incident reports: 18 in the API response, none overlapping any of the 34 study dates
  (`incidents_on_study_dates` is empty). The nearest is 2025-08-29 06:18 to 06:37 UTC.

## HEAD does not work on datasets.tardis.dev

- Every one of the 68 HEAD requests returned HTTP 404 with no Content-Length, for all
  three splits. This is a property of the server, not of the files: HEAD also returns 404
  for a symbol that does not exist, while a GET of the same train-day URL returns 200 with
  the size. Range requests are blocked by Cloudflare (403).
- Consequence: AC0.1 ("each HTTP 200 with a positive content-length") cannot pass with
  HEAD, and this session forbids any GET of a test-day file. AC0.1 fails until Ilia
  decides. [TBD: Q1 below.]
- For train and val dates only, recon.json also holds a `get_headers` record: a GET whose
  response body is never read; the connection is closed after the headers. The split lock
  is checked before each one. All 36 returned 200 with a size. This departs from "HEAD
  only" for non-test days; nothing was written to disk by it.

## Sizes per split (compressed CSV, from `get_headers`)

| Split | Days | incremental_book_L2 bytes | trades bytes | Total bytes |
|---|---|---|---|---|
| train | 12 | 7,334,008,591 | 399,188,893 | 7,733,197,484 |
| val | 6 | 3,234,794,746 | 138,245,605 | 3,373,040,351 |
| test | 16 | unknown (HEAD only) | unknown (HEAD only) | unknown |

- Per day, the book file ranges from 250,916,612 bytes (2024-06-01) to 941,657,804 bytes
  (2024-05-01). 2024-01-01 is 546,329,028 (book) plus 20,848,659 (trades).
- Disk: train plus val raw is 11.1 GB. On 2024-01-01 the converted parts took 1.37 times
  the raw bytes, so M1 needs about 26 GB for raw plus converted. This disk had 7.6 GiB
  free after M0. [TBD: Q4 below.]

## Venue (configs/venue.yaml)

- Tick 0.10 USDT, lot (step and minimum quantity) 0.001 BTC on all 34 dates.
- Minimum notional 100 USDT from 2023-11-02 to the change at 2026-04-14 06:30 UTC, then
  50 USDT. So 2026-05-01 to 2026-10-01 (six test days) use 50.
- Regular user (VIP 0) fees, no BNB discount: maker 2.0 bp, taker 5.0 bp on all 34 dates.
- Sources: for each date a Wayback capture of Binance's exchangeInfo or of a Binance page
  carrying the same filters before and after the date, and of the fee-schedule endpoint.
  Full list with quotes: docs/venue_sources.json. I re-fetched three of them (exchangeInfo
  2024-01-01 22:00 and 2026-05-10 10:00, fee schedule 2023-12-23) and the 2026-04-09
  announcement of the notional change, and they match.
- Tick inferred from the 2024-01-01 data: 0.1, the most common gap between distinct book
  prices. 233 of 97,848,907 book rows and 114 of 2,279,325 trade rows sit off the 0.1 grid
  (on 0.01, for example 42335.75). Lot inferred from trade sizes: 0.001, no rows off grid.
  [TBD: Q5 below.]
- A published maker rebate exists: the USD-M Futures Liquidity Provider Program, maker fee
  from -0.1 bp (Tier 1) to -0.5 bp (Tier 4) on USDT pairs since 2025-03-03, open on
  application to accounts with at least 100M USD of 30-day futures volume. Source:
  https://www.binance.com/en/support/announcement/detail/cde392fe431a4045a951d40d7498abbc.
  [TBD: Q6 below.]

## Benchmark

One day, 2024-01-01, measured on 2026-10-22 (data/benchmark_m0.json, data/converted/2024-01-01/convert.json).

| Item | Value |
|---|---|
| Raw bytes (book plus trades, gzip CSV) | 567,177,687 |
| Rows | 96,295,836 book, 2,197,331 trades |
| Converted bytes (7 compressed npz parts) | 776,082,982 |
| Events after conversion | 100,128,234 |
| Conversion time | 150.1 s (one process; peak RSS 7.3 GB) |
| Order-latency build (feed latency x 1, 1 s samples) | 12.2 s, 86,406 rows |
| Loop wall time | 16.7 s, plus 4.7 s numba compile and first-part load once per process |
| Fill count | 32,854 |
| Steps quoted | 845,400 (every 100 ms from 00:30:00 to 23:59:00) |
| Backtest peak RSS | 4,182,736,896 bytes (3.9 GiB) |
| Machine | Apple M1 Pro, 8 cores (6 performance, 2 efficiency), 16 GiB RAM, macOS 26.0, Python 3.12.13, hftbacktest 2.4.4 |

- Loop: B0 with h = 1 tick (bid = mid - 1 tick rounded down, ask = mid + 1 tick rounded
  up), post-only, order size 0.003 BTC (the smallest whole number of lots reaching 100
  USDT at the first quoting mid), inventory cap 10 order sizes, risk-averse queue model,
  `no_partial_fill_exchange()`, order latency equal to feed latency, fees zero.
- The end-of-day gross PnL in data/benchmark_m0.json is kept only for the M2 accounting
  checks. It is not a result.
- `partial_fill_exchange()` panicked on this day (`partialfillexchange.rs:251`, an unwrap
  of a missing order in `remove_filled_orders`), with price-tick order ids and again with
  unique ids. `no_partial_fill_exchange()` ran the same loop without error. [TBD: Q3 below.]
- With a one-tick spread the mid sits half a tick inside, so h = 1 rounds outward to one
  tick behind the best price on each side. [TBD: Q8 below.]

## Compute projection

From `uv run python scripts/compute_projection.py 8` (output pasted below). Assumptions:
a day-run costs the 2024-01-01 loop time scaled by that day's book-file size; test days
have the mean train and val size, because HEAD gives no size; B1, B2, B2b and B3 cost the
same as B0, which is a lower bound until M2 and M3 time them; about 8 GiB of RAM is free
for runs (40 to 61 percent of 16 GiB was free during M0), so 2 runs fit side by side at
3.9 GiB each even though there are 8 cores.

- Loop cost: 16.7 s for 546,329,028 book bytes.
- Mean seconds per day-run: train 19, val 16, test 18.
- Usable parallel runs: 2 (memory bound, not core bound).

| Item | Day-runs | Core-hours | Wall-clock hours at 2 parallel |
|---|---|---|---|
| M4 tuning (63 candidates x 6 val days, primary cell) | 378 | 1.7 | 0.9 |
| M4 canaries C1 to C4 and B1 reference, val days | 36 | 0.2 | 0.1 |
| M4 MDE, B2b and B3 on train days | 24 | 0.1 | 0.1 |
| M5 B1, B2, B2b, B3 in all 8 cells, 16 test days | 512 | 2.6 | 1.3 |
| M5 canaries, primary cell only | 80 | 0.4 | 0.2 |
| M5 canaries in every cell (upper case) | 576 | 2.9 | 1.4 |
| M4 total (canaries primary cell) | 438 | 2.0 | 1.0 |
| M5 total (canaries primary cell) | 592 | 3.0 | 1.5 |

- One-time costs not in the table: conversion at about 150 s per day (34 days, about
  1.4 hours) and one order-latency file per day and latency setting (about 12 s each).
- The compute rule in SPEC.md M0 compares the M5 figure with Ilia's limit.
  [TBD: Q7 below.]

## Open questions for Ilia

1. AC0.1 cannot pass: HEAD returns 404 for every file. Options: (a) allow a header-only
   GET for test days (body never read, nothing written; still a GET of a test-day URL);
   (b) accept the Tardis API listing (BTCUSDT incremental_book_L2 and trades available to
   2026-10-22, no incident on a study date) as the availability check and change AC0.1
   in scripts/check_milestone.py; (c) leave AC0.1 open until M5, where exclusion rule 1
   handles a missing file. Also confirm that the header-only GETs already made for train
   and val days are acceptable.
2. Queue-model variants: PREREGISTRATION.md names power n = 3, power n = 2 and log.
   hftbacktest 2.4.4 has three power and two log variants. Proposed:
   `power_prob_queue_model(3.0)`, `power_prob_queue_model(2.0)`, `log_prob_queue_model()`
   (docs/ENGINE.md, Queue models).
3. Exchange model for PREREGISTRATION.md section 3: `partial_fill_exchange()` panics in
   2.4.4 on 2024-01-01 (see Benchmark). Proposed: `no_partial_fill_exchange()`, the
   hftbacktest default, with the limitation that an order at the front of the queue fills
   in full on any trade at its price. Report the panic upstream?
4. Disk: M1 needs about 26 GB (11.1 GB raw for train and val plus about 15 GB converted);
   7.6 GiB was free after M0. The uv cache in ~/.cache/uv is 7.4 GiB. Free space, add a
   drive, or keep converted parts for only a few days at a time (re-conversion takes about
   150 s per day)?
5. 233 book rows and 114 trades on 2024-01-01 sit on a 0.01 grid although the tick is
   0.10. Keep them as they are, or treat them as a data-quality item in M1?
6. Third fee level for PREREGISTRATION.md section 6: the Liquidity Provider Program's
   Tier 1 maker fee of -0.1 bp (published, needs 100M USD of 30-day volume), or a labelled
   hypothetical? Also: model the BTCUSDT add-on (an extra -0.05 bp, 2025-11-12 to
   2026-02-08)?
7. Compute limit in wall-clock hours for the M5 rule in SPEC.md.
8. B0 with h = 1 quotes one tick behind the best price when the spread is one tick, as
   the outward rounding in section 4 implies. Intended?
9. Order size: fixed for the day from the first quoting mid. On a day when the price falls
   enough, 3 lots can drop below the minimum notional, which the exchange would reject.
   Keep the fixed size, or recompute per order from the current mid?
10. Canaries in M5: primary cell only (PREREGISTRATION.md section 10), or every cell (the
    SPEC.md compute rule lists "canaries in the primary cell only" as a reduction)?
11. Order latency is interpolated between 1 s samples, so the latency applied at t uses
    feed latency up to 1 s later (docs/ENGINE.md, Latency models). Accept, or use the
    sample at or before t only (needs a custom latency array, not engine changes)?
