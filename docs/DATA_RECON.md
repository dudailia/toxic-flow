# Data recon (M0)

What the data source and the venue look like before anything is designed around them.
Records behind every number below: data/recon.json (scripts/recon.py),
data/converted/2024-01-01/convert.json (make data), data/benchmark_m0.json
(scripts/benchmark_m0.py), configs/venue.yaml and docs/venue_sources.json.

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
- The recorder's websocket endpoint changed during the test period: `wss://fstream.binance.com/stream`
  until 2026-03-18 12:07:41 UTC, `wss://fstream.binance.com/public/stream` after
  (`dataCollectionDetails.wssConnectionChanges`). All 18 train and val days and the first 9
  test days use the old endpoint; the last 7 test days (2026-04-01 to 2026-10-01) the new
  one. [TBD: Q12 below.]
- Incident reports: 18 in the API response, none overlapping any of the 34 study dates
  (`incidents_on_study_dates` is empty). The nearest is 2025-08-29 06:18 to 06:37 UTC.

## HEAD does not work on datasets.tardis.dev

- Every one of the 68 HEAD requests returned HTTP 404 with no Content-Length, for all
  three splits. It is the server, not the files. Running `server_probes()` from
  scripts/recon.py at 2026-10-22 16:08:08 UTC gave: HEAD 404 for the 2024-01-01 trades
  file and 404 for a symbol that does not exist; a GET of the same file 200 (400 for the
  missing symbol); a byte-range GET 403. These probes are not yet in the committed
  recon.json: the recon run meant to record them hit HTTP 429 with `Retry-After: 79529`
  (about 22 hours), after two complete and three partial recon runs that day. recon.py records them
  on its next run. [TBD: Q16 below.]
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
  the raw bytes, so M1 needs about 26 GB for raw plus converted. Free disk when the
  benchmark finished: 7,971,573,760 bytes (`free_disk_bytes_at_end`). [TBD: Q4 below.]

## Venue (configs/venue.yaml)

- Tick 0.10 USDT, lot (step and minimum quantity) 0.001 BTC on all 34 dates.
- Minimum notional 100 USDT from 2023-11-02 to the change at 2026-04-14 06:30 UTC, then
  50 USDT. So 2026-05-01 to 2026-10-01 (six test days) use 50.
- Regular user (VIP 0) fees, no BNB discount: maker 2.0 bp, taker 5.0 bp on all 34 dates.
- Sources: for each date a Wayback capture of Binance's exchangeInfo or of a Binance page
  carrying the same filters before and after the date, and of the fee-schedule endpoint.
  Full list: docs/venue_sources.json. On 2026-10-22 I re-fetched three of these captures
  (exchangeInfo at 2024-01-01 22:00 and 2026-05-10 10:00 UTC, fee schedule at 2023-12-23)
  and the 2026-04-09 announcement of the notional change, and each matched the table.
- Tick inferred from the 2024-01-01 data (`inferred` in convert.json): 0.1, the most common
  gap between distinct book prices. 201 of 96,295,836 book rows and 101 of 2,197,331 trade
  prices sit off the 0.1 grid (on 0.01). Lot inferred from trade sizes: 0.001, no rows off
  that grid. [TBD: Q5 below.]
- A published maker rebate exists: the USD-M Futures Liquidity Provider Program, maker fee
  from -0.1 bp (Tier 1) to -0.5 bp (Tier 4) on USDT pairs since 2025-03-03, open on
  application to accounts with at least 100M USD of 30-day futures volume. Source:
  https://www.binance.com/en/support/announcement/detail/cde392fe431a4045a951d40d7498abbc.
  [TBD: Q6 below.]

## Benchmark

One day, 2024-01-01 (convert.json and benchmark_m0.json, measured 2026-10-22).

| Item | Value |
|---|---|
| Raw bytes (book plus trades, gzip CSV) | 567,177,687 |
| Rows | 96,295,836 book, 2,197,331 trades |
| Converted bytes (7 compressed npz parts) | 776,082,982 |
| Events after conversion | 100,128,234 |
| Conversion time | 153.3 s, process peak RSS 7,545,012,224 bytes |
| Order-latency build (feed latency x 1, 1 s samples) | 11.2 s, 86,406 rows |
| Order entry latency (= feed latency) | p50 3.252 ms, p90 3.917 ms, p99 9.823 ms, max 1,913 ms (the REST snapshot) |
| Loop wall time | 15.5 s, plus about 4.5 s numba compile and first-part load once per process |
| Fill count | 31,464 |
| Steps quoted | 845,399 (every 100 ms from 00:30:00 to before 23:59:00) |
| Orders resting on one side, at most | 1 |
| Inventory, largest | 10 order sizes (the cap) |
| Backtest peak RSS | 4,150,591,488 bytes (3.87 GiB) |
| Machine | Apple M1 Pro, 8 cores (6 performance, 2 efficiency), 16 GiB RAM, macOS 26.0, Python 3.12.13, hftbacktest 2.4.4 |

- Loop: B0 with h = 1 tick (bid = mid - 1 tick rounded down, ask = mid + 1 tick rounded
  up), post-only, one order per side (a replace waits for its cancel), order size 0.003
  BTC (the smallest whole number of lots reaching 100 USDT at the first quoting mid),
  inventory cap 10 order sizes, risk-averse queue model, `no_partial_fill_exchange()`,
  order latency equal to feed latency, fees zero. No decision at or after 23:59:00; all
  orders are cancelled then and inventory is marked at that mid.
- The end-of-day gross PnL in data/benchmark_m0.json is kept only for the M2 accounting
  checks. It is not a result.
- `partial_fill_exchange()` panicked on this day (`partialfillexchange.rs:251`, an unwrap
  of a missing order in `remove_filled_orders`), with price-tick order ids and again with
  unique ids. `no_partial_fill_exchange()` ran the same loop without error. [TBD: Q3 below.]
- With a one-tick spread the mid sits half a tick inside, so h = 1 rounds outward to one
  tick behind the best price on each side. [TBD: Q8 below.]

## Compute projection

From `uv run python scripts/compute_projection.py`, which reads benchmark_m0.json and
recon.json. Assumptions: a day-run costs the 2024-01-01 loop time scaled by that day's
book-file size; test days have the mean train and val size, because HEAD gives no size;
B1, B2, B2b and B3 cost the same as B0, which is a lower bound until M2 and M3 time them;
free RAM is the 8.33 GiB the benchmark recorded as available, so 2 runs of 3.87 GiB fit
side by side even though there are 8 cores.

- Loop cost: 15.5 s for 546,329,028 book bytes.
- Mean seconds per day-run: train 17, val 15, test 17.
- Usable parallel runs: 2 (memory bound, not core bound).

| Item | Day-runs | Core-hours | Wall-clock hours at 2 parallel |
|---|---|---|---|
| M4 tuning (63 candidates x 6 val days, primary cell) | 378 | 1.6 | 0.8 |
| M4 canaries C1 to C4 and B1 reference, val days | 36 | 0.2 | 0.1 |
| M4 MDE, B2b and B3 on train days | 24 | 0.1 | 0.1 |
| M5 B1, B2, B2b, B3 in all 8 cells, 16 test days | 512 | 2.4 | 1.2 |
| M5 canaries, primary cell only | 80 | 0.4 | 0.2 |
| M5 canaries in every cell (upper case) | 576 | 2.7 | 1.3 |
| M4 total (canaries primary cell) | 438 | 1.9 | 0.9 |
| M5 total (canaries primary cell) | 592 | 2.7 | 1.4 |

- One-time costs not in the table: conversion at about 150 s per day (34 days, about
  1.4 hours) and one order-latency file per day and latency setting (about 11 s each).
- The compute rule in SPEC.md M0 compares the M5 figure with Ilia's limit.
  [TBD: Q7 below.]

## Open questions for Ilia

1. AC0.1 cannot pass: HEAD returns 404 for every file (see `server_probes`). Options: (a)
   allow a header-only GET for test days (body never read, nothing written; still a GET
   of a test-day URL); (b) accept the Tardis API listing (BTCUSDT incremental_book_L2 and
   trades available to 2026-10-22, no incident on a study date) as the availability check
   and change AC0.1 in scripts/check_milestone.py; (c) leave AC0.1 open until M5, where
   exclusion rule 1 handles a missing file. Also confirm that the header-only GETs already
   made for train and val days are acceptable.
2. Queue-model variants: PREREGISTRATION.md names power n = 3, power n = 2 and log.
   hftbacktest 2.4.4 has three power and two log variants. Proposed:
   `power_prob_queue_model(3.0)`, `power_prob_queue_model(2.0)`, `log_prob_queue_model()`
   (docs/ENGINE.md, Queue models).
3. Exchange model for PREREGISTRATION.md section 3: `partial_fill_exchange()` panics in
   2.4.4 on 2024-01-01. Proposed: `no_partial_fill_exchange()`, the hftbacktest default.
   Its limitation reaches the primary cell: after a half-lot overshoot of the queue the
   whole 3-lot order fills, which biases gross PnL per notional upward (docs/ENGINE.md,
   Exchange model). Measure the share of such fills on a train day in M2? Report the
   panic upstream?
4. Disk: M1 needs about 26 GB (11.1 GB raw for train and val plus about 15 GB converted);
   8.0 GB was free after M0. Free space, add a drive, or keep converted parts for only a
   few days at a time (re-conversion takes about 150 s per day)?
5. 201 book rows and 101 trade prices on 2024-01-01 sit on a 0.01 grid although the tick
   is 0.10. Keep them as they are, or make them a data-quality item in M1?
6. Third fee level for PREREGISTRATION.md section 6: the Liquidity Provider Program's
   Tier 1 maker fee of -0.1 bp (published, needs 100M USD of 30-day volume), or a labelled
   hypothetical? Also: model the BTCUSDT add-on (an extra -0.05 bp, 2025-11-12 to
   2026-02-08)?
7. Compute limit in wall-clock hours for the M5 rule in SPEC.md.
8. B0 with h = 1 quotes one tick behind the best price when the spread is one tick, as
   the outward rounding in section 4 implies. Intended?
9. Order size: fixed for the day from the first quoting mid, and the minimum notional is
   checked at that mid, not at the order's own price. On a day when the price falls
   enough, 3 lots can drop below the minimum notional, which the exchange would reject.
   Keep the fixed size, or recompute per order from the order price?
10. Canaries in M5: primary cell only (PREREGISTRATION.md section 10), or every cell (the
    SPEC.md compute rule lists "canaries in the primary cell only" as a reduction)?
11. Order latency (docs/ENGINE.md, Latency models): it is interpolated between 1 s samples,
    so the latency applied at t uses feed latency up to 1 s later; the REST snapshot
    enters as a 1.9 s sample; the timestamp offset is one value per day. Proposed for M1:
    build the latency samples from non-snapshot events only and report each day's offset.
    Accept the 1 s interpolation, or use only the sample at or before t (a custom latency
    array, no engine change)?
12. The Tardis websocket endpoint changed on 2026-03-18 (9 test days before, 7 after), and
    the minimum notional changed on 2026-04-14. Pre-register, before the tag, a test-day
    check of feed-latency quantiles and event rates against the train and val range, and
    an exploratory H1 split by endpoint?
13. A ConversionError from src/toxic_flow/data/convert.py (no clean cut, a snapshot that
    would be truncated, a cut through a snapshot) is a failure of the splitter, not of
    hftbacktest, so it is not exclusion rule 2. What should happen on such a day? Proposed:
    dry-run the splitter on all 18 train and val days in M1 and pre-register the fallback
    (for example a wider window or fewer parts) before the tag.
14. The split lock accepts a lightweight tag and any remote named origin. Add checks that
    prereg-v1 is an annotated tag and that origin is the public GitHub repo? Both files
    are protected, so this needs your approval.
15. Deferred from code review, minor: `order_size` uses the lot as the minimum quantity
    (they are equal on all 34 dates); two `make data` runs on the same day at once would
    share a `.part` file; the converter reads each gzip file twice (row count, then
    parse).
16. Tardis rate limit: after two complete and three partial recon runs (a complete run is
    68 HEAD and 36 header-only GETs) and
    one day's download, datasets.tardis.dev answered 429 with `Retry-After: 79529` s.
    M1 downloads 36 files. Download at most a few days per session, or get an API key?
    Recon does not need to run again for M0.
