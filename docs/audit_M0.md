# M0 review record

Two rounds of two independent, read-only reviews on 2026-10-22: the leakage-auditor agent
and /code-review at high effort. Round 1 covered commits 282ddbf..970fa0c (fixes in
a967f6f); round 2 covered 282ddbf..67b20c4, after the AC0.1 decision. Open items point to
the questions in docs/DATA_RECON.md.

## Round 1

### Leakage auditor

Summary of its report: no path in M0 downloads, converts or reads a test-day file, and no
forward-looking input reaches the B0 quote decision. Checked and cleared: no test date in
the manifest, recon.json, any path under data/ or the temp folders; the lock commit
(13:53 UTC) precedes the first download (14:10 UTC); the 32 test-day requests in
recon.json were HEAD (round 2 found more HEADs outside recon.json, see below); the converter's clean-cut argument (its own trace of `correct_event_order`, plus the
6 real cuts monotone in both orders with 51 to 54 ms gaps); B0 causality; layering;
venue.yaml against docs/venue_sources.json.

| # | Finding | Status |
|---|---|---|
| 1 | Tardis websocket endpoint changed on 2026-03-18, splitting the test days 9 and 7 | Documented in DATA_RECON.md; Q12 |
| 2 | Converter failures are not hftbacktest failures, so not exclusion rule 2 | Snapshot-count false alarm fixed; governance stated in convert.py; Q13 |
| 3 | Risk-averse queue plus no-partial-fill fills the whole order after a half-lot overshoot | Documented in ENGINE.md; Q3 |
| 4 | Order latency includes the REST snapshot sample and a day-wide offset | Documented in ENGINE.md; quantiles now in benchmark_m0.json; Q11 |
| 5 | B0 end of day did not match section 3 | Fixed: no decision at or after quote end, mark at that mid |
| 6 | Lock accepts a lightweight tag and any remote named origin | Open, protected file; Q14 |
| 7 | Some DATA_RECON numbers were not in a committed record or counted events as rows | Fixed: counts now from CSV rows in convert.json, RAM and disk in benchmark_m0.json. The server probe results are in DATA_RECON.md with their time; the run meant to record them was rate-limited (Q16), and since the AC0.1 decision recon.py sends no dataset request |

### Code review

| Finding | Status |
|---|---|
| Snapshot check counted rows that `correct_event_order` duplicates, failing correct days | Fixed; test with an update that overtakes a snapshot |
| B0 could hold several orders per side while cancels were in flight, passing the cap | Fixed; test at 250 ms latency saw 4 per side before, 1 after |
| Inferred counts were event counts, not rows | Fixed; test against CSV row counts |
| Splitter raises where hftbacktest would not | Wider window tried before failing; governance Q13 |
| A cut could fall between a snapshot block and its closing row | Fixed; unit test on find_cuts |
| Crash between placing a raw file and pinning it blocks later runs | Fixed: pin first; test with a simulated crash |
| B0 quoted at or after 23:59:00 and marked one second late | Fixed; test, and a mutation to the old order fails it |
| order_size ignores min_qty and checks notional at mid | Deferred: min_qty equals the lot on all 34 dates; Q9, Q15 |
| Price-tick order ids could block a quote | Fixed: ids are never reused |
| Fixed `.part` name shared by two concurrent runs | Deferred; Q15 |
| Untraceable numbers in DATA_RECON.md | Fixed (as auditor item 7) |
| No run-time check that cuts are increasing and clean | Fixed; tests for both |
| Each gzip file read twice | Deferred; Q15 |
| Smoke test used models the study does not use | Fixed: no-partial-fill and feed-based latency |
| Lock does not require an annotated tag | Open, protected file; Q14 |

### Found while fixing

hftbacktest keeps a raw pointer to an ndarray passed to `data()` or
`intp_order_latency()` without copying it. A B0 smoke test passed a local array and two of
four full test runs aborted. Tests and the benchmark now pass file paths; three full runs
in a row then passed. docs/ENGINE.md records the rule for M2.

## Round 2

### Leakage auditor

Summary: no code path can download, convert or read a test-day file before prereg-v1, and
every test-day contact on record was a HEAD that returned 404 with no body; HEAD also
returns 404 for a symbol that does not exist, so these requests revealed nothing.

| # | Finding | Status |
|---|---|---|
| 1 | DATA_RECON's account of test-day requests left out run A (13:54 to 14:04 UTC) | Fixed: every run listed in data/recon_logs/2026-10-22_recon_runs.txt and DATA_RECON.md; Q17 |
| 2 | AC0.1 read only recon.json and passed when its test rows were deleted or changed; TardisClient had no lock and no log | Fixed: the 32 rows pinned by count and hash, statuses checked, recon_logs checked, every request logged before it is sent, test-day dataset URLs refused in TardisClient (leakage tests) |
| 3 | Exclusion rule 1 cannot tell a rate limit from a missing file | Open, PREREGISTRATION.md; Q18 |
| 4 | The 429 in force came from an ad-hoc call the client never saw; date-form Retry-After | Fixed: wait file seeded (no request before 2026-10-23 15:26:43 UTC); date form parsed |

### Code review

| Finding | Status |
|---|---|
| Retry-After as an HTTP date raised ValueError, so the wait was dropped | Fixed; test |
| AC0.1 passed while DATA_RECON listed HEADs outside recon.json | Fixed with auditor item 2; Q17 |
| Split lock trusts whatever URL origin has | Open, protected file; Q14 |
| convert.json was gitignored, so DATA_RECON numbers had no committed record | Fixed: convert.json committed |
| Local disk errors counted as Tardis failures; no free-space check | Fixed: DiskSpaceError before any byte is written; test |
| http.client protocol errors escaped the failure count | Fixed; test |
| Failed conversion left its staging directory | Fixed; test |
| Raw file made read-only only after it was placed | Fixed: read-only before os.link; test with a simulated crash, and one for a stale read-only .part |
| Snapshot block span from first and last rows, not min and max | Fixed; test |
| Header-only file gave a TypeError | Fixed: ConversionError; test |
| ru_maxrss is KiB on Linux | Fixed: machine.peak_rss_bytes; test |
| Ongoing incident without an end crashed recon | Fixed; test |
| No test of the re-fetch of an evicted raw file | Added; it passed as written |
| TardisClient did not itself enforce "no retry of a failed URL" | Fixed: failed URLs refused; test |
| Benchmark warm-up decompresses part 0 to read one timestamp | Deferred, minor: changing it means re-measuring |
