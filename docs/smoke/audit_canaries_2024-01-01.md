# Leakage audit of SMOKE run 683bdb67ceee (canaries, 2024-01-01)

Why it ran: CLAUDE.md requires the leakage-auditor when any run beats its zero-latency
twin. In this run three did: B3 (BEF -0.869 bp at high latency, -0.881 bp at zero),
C4 at x0.1 (-0.859 and -0.868) and C4 at x10 (-0.888 and -0.889). B1, C1 and C2 did
better at zero latency. The auditor read the code and re-ran single cells on 2024-01-01
in a scratch directory. It edited nothing and made no network request.

## Verdict

Explainable without leakage or a bug. Latency changes which orders fill, so the high and
zero runs trade different fill sets: about 2,030 fills are common to both B3 runs, and
the gap comes from about 500 and 430 fills that only one run has. Evidence:

- Paired hourly block bootstrap of B3, high minus zero (24 hours, 20,000 resamples):
  +0.0125 bp, interval [-0.014, +0.040]. High is ahead in 13 of 24 hours.
- The same high-latency file shifted in time (9 schedules from 2 s earlier to 1 h later)
  gives B3 a BEF from -0.887 to -0.868. Zero's -0.881 is inside that range.
- A constant 9.76 ms latency (the high file's median) gives -0.888, worse than zero.
- B1 at zero beats every high-latency variant tried.

## Findings

| # | Finding | Effect here | Action |
|---|---|---|---|
| 1 | C1 shuffles signs only, so its magnitude m, and the widening d m, stay as in B3. Section 10 compares C1 with B1, so with d > 0 the interval can exclude 0 without any sign information. | None (one day, no interval) | Q28 for Ilia before the tag |
| 2 | C4 keeps B3's K. K computed for each variant: 7.665 (x10) and 2.006 (x0.1), against 3.464 for B3. Mean m under B3's K is 0.087 and 0.043, against 0.053 and 0.070 under their own. | None | Q25, now with these numbers |
| 3 | The C3 flag and the CLAUDE.md trigger compare means. On one day the noise (sd about 0.01 bp) is as large as the latency effect, so both fire often by chance. | Triggered this audit | Q29 |
| 4 | generate_order_latency keeps one feed-latency row per second and the interpolation uses the rows on both sides of t, so order latency at t depends on feed latency up to 1 s later. The strategy cannot read latency, and the timing sweep shows no gain from it. | None | Limitation to state; Q30 |
| 5 | Quote presence was 1.0 by construction in the B1 and overlay loops. | Metric wrong in all three smoke runs; fills, PnL, BEF and markouts unaffected | Fixed in 679c894 with a test; smoke reports now say the column is not valid |
| 6 | Row order inside fills files follows hash-map order. Fill sets and metrics are identical across runs. | None | None |

Checked with no issue: zero latency is constant_order_latency(0, 0), with feed latency
still in the data; the high-latency file is three times the low one; the overlay loop
reads events, OFI and the C2 series only at or before now; C2's series reaches only C2,
and B1, B3, C1 and C4 reproduce exactly without the oracle; C1 and C4 match section 10
apart from K; gross PnL reconciles with the engine in all 12 rows; every net PnL at the
2.0 bp maker fee is negative, C2 included (-139.9 and -144.7 USDT).
