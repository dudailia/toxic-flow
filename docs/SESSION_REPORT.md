# Session report, 2026-10-22 (unattended block)

Rules for the block, all kept: no edit to any path in .claude/protected-paths.txt (anything
that belongs there is a complete file in docs/proposals/, new leakage tests are in
tests/pending_leakage/); no request to any tardis.dev URL (data/tardis_requests.jsonl is
still empty, and data/tardis_wait.json blocks requests until 2026-10-23 15:26:43 UTC); a
commit and push after each item. The only network traffic was git pushes and reading the
hftbacktest GLFT tutorial from GitHub at the pinned tag.

## What was done

| # | Item | Commit | Where |
|---|---|---|---|
| 1 | Q14: stricter lock as complete files, tested in a clean clone | 31fcbe8 | configs/repo.yaml, docs/proposals/Q14/ |
| 2 | Q17 disclosure and Q18 exclusion rule 1 in PREREGISTRATION.md section 2 | efa249e | PREREGISTRATION.md |
| 3 | M1 on 2024-01-01: data-quality report, market-order events, AC1.4 and AC1.5 tests | a147f33 | data/book.py, data/validate.py, events/market_orders.py, docs/data_quality/2024-01-01.json |
| 4 | M3 on synthetic data: Hawkes likelihood, fit, simulator, online intensity, EWMA; AC3.1 to AC3.3 tests | 7717dee | signals/, tests/unit/test_hawkes.py, tests/pending_leakage/ |
| 5 | OFI (B2 signal) and a smoke run on 2024-01-01 | e4aecb6 | signals/ofi.py, docs/signals/ofi_2024-01-01.json |
| 6 | Proposed M1 and M3 checks with a dry run | 529220f | docs/proposals/check_M1_M3.md |
| 7 | M2 harness: grid, run, B0 and B1 loops, metrics, markouts | 1dcb6bb | engine/, strategies/, eval/ |
| 8 | AC2.2 and AC2.3 tests on 2024-01-01; AC2.6 layering test | 0fbfb4f | tests/unit/test_accounting.py, tests/pending_leakage/test_layering.py |
| 9 | SMOKE grid on 2024-01-01, B0 h = 1 and B1 placeholder gamma, 8 cells | 7cc72b8, bcb19b5 | configs/runs/smoke_2024-01-01.yaml, results/5b1da521ba25/, docs/smoke/smoke_2024-01-01.md |
| 10 | Paper scaffold: template, build, AC6.1 checker | 315e327 | paper/ |
| 11 | Proposed M2 checks with a dry run | 0eaa2e0 | docs/proposals/check_M2.md |

### Highlights by item

1. Q14. Against the current lock, the proposed tests fail for a lightweight tag, an origin
   other than configs/repo.yaml, and a missing configs/repo.yaml; all 15 pass against the
   proposed lock, and the whole fast suite passes with it (docs/proposals/Q14/RESULTS.md).
   The hash-mismatch test passes against the current lock too, because (c) was already
   enforced. Also proposed: add configs/repo.yaml to .claude/protected-paths.txt.
2. PREREGISTRATION.md section 2 now discloses the recon HEADs (64 recorded, at most 128 in
   all, every one 404 with no body, no GET) and states the new rule 1.
3. 2024-01-01: 2,197,331 prints collapse into 598,584 market-order events (ratio 3.67, up
   to 397 prints in one event). Feed latency p50 3.4 ms (book) and 4.5 ms (trades), p99
   22.6 and 87.8 ms. Largest gaps in the quoting window 0.49 s (book) and 7.0 s (trades),
   so no exclusion. Book updates plus snapshot rows equal the CSV's 96,295,836 rows.
4. Hawkes: the O(n) log-likelihood equals the O(n^2) definition to 1e-10 with tied
   timestamps; online intensity equals the offline formula to 1e-9 (AC3.2); the fit
   recovers all seven parameters within 3 standard errors from 56,472 simulated events
   (AC3.3; table below). A bug found and fixed on the way: an event at exactly t = 0 ns
   was treated as "no event yet".
5. OFI on 2024-01-01 (smoke, nothing chosen): 3.6M book states; OFI_W correlates with the
   mid change over the same window at 0.65, 0.74 and 0.77 for W = 1, 5 and 30 s.
6. Dry runs: M1 passes 7 of 12 (one of 18 days present), M3 passes 7 of 11.
7. B0 refactored onto shared helpers reproduces the M0 benchmark exactly (31,464 fills).
   B1 follows the hftbacktest GLFT tutorial's estimation.
8. AC2.2: gross PnL from the recorded fills equals hftbacktest's cash plus inventory at the
   mark to 1e-6 USDT for B0 and B1. AC2.3: a run with hftbacktest's own 2 bp maker fee
   gives the same net PnL as the post-hoc fee, to 1e-6 USDT.
9. SMOKE: the risk-averse model has the fewest fills of the four queue models for B0 and
   B1 at both latencies (AC2.4 preview). Every cell loses money before fees (break-even
   fee -0.83 to -0.98 bp), as section 1 expects; nothing looked too good, so no audit was
   triggered. configs/selected.yaml was not written.
10. make paper stops cleanly while results/summary.json does not exist; the real template
    passes the AC6.1 check with a dummy summary.
11. Dry run: M2 passes 6 of 11 (AC2.2 over the 16 smoke rows with a largest gap of 7e-12
    USDT, and AC2.3).

## Test results

Commands run at the end of the block:

- `make check`: exit 0, 173 passed, 8 deselected (slow).
- `uv run pytest tests`: 181 passed in 78 s, slow tests included.
- AC1.4, AC1.5, AC3.1 (EWMA at tau 1 s and 30 s, Hawkes, OFI, three seeds each), AC3.2
  and AC3.3: 25 passed.
- AC2.2 and AC2.3 (slow, 2024-01-01): 3 passed.
- `uv run python scripts/check_milestone.py M0`: 21/21, exit 0.

AC3.3 recovery, four pooled simulated days of 7,000 s:

| Parameter | True | Fit | SE | z |
|---|---|---|---|---|
| mu_b | 0.6 | 0.5952 | 0.0084 | -0.57 |
| mu_s | 0.4 | 0.4044 | 0.0067 | +0.66 |
| alpha_bb | 0.8 | 0.8033 | 0.0157 | +0.21 |
| alpha_bs | 0.3 | 0.3194 | 0.0138 | +1.41 |
| alpha_sb | 0.2 | 0.2052 | 0.0089 | +0.58 |
| alpha_ss | 0.7 | 0.7200 | 0.0157 | +1.27 |
| beta | 2.0 | 2.0242 | 0.0372 | +0.65 |

Branching ratio 0.5044 against a true 0.5.

## Judgment calls to check

Engine and data
1. hftbacktest's book never shows best bid at or above best ask: a crossing update moves
   the opposite best past it (HashMapMarketDepth::update_bid_depth), and that side stays
   empty until its next update. "Crossed" in the data-quality report therefore counts an
   opposite level hidden within 10 ticks of the touch, plus one-sided batches. Deeper
   overlaps are missed. On 2024-01-01 both counts are 0.
2. The same behaviour matters for the strategies: after a crossing update B0 and B1 see an
   empty side and do not quote until it returns. It never happened on 2024-01-01.
3. The replay's last batch of a day is applied but returned as end of data, so it is not a
   row (one batch per day).
4. Queue-model variants in the grid are my proposal (Q2): power_prob_queue_model(3.0),
   power_prob_queue_model(2.0), log_prob_queue_model(). The exchange model is
   no_partial_fill_exchange() (Q3).

Signals and events
5. A market-order event takes the local time of its last print: it is complete only then.
6. In the Hawkes fit, events at the same instant do not excite one another (strict t_i < t);
   at decision times the online intensity includes events with local_ts at or before t, as
   section 5 says.
7. Hawkes fit: L-BFGS-B on log-parameters from a start of half of each rate as baseline,
   excitation 0.25 and beta 1; standard errors from a central-difference Hessian with
   steps of 1e-4 of each parameter.
8. OFI contributions are taken between consecutive book states at distinct local
   timestamps, so events received in the same instant are aggregated. u is 0 until the
   30-minute normaliser has 18,000 values.

Strategies and evaluation
9. B1 follows the hftbacktest GLFT tutorial for estimation (10-minute window, refit every
   5 s, 70 depth levels, xi = gamma, delta = 1), with two departures section 4 requires:
   quotes round outward and are not capped at the best price, and the cross guard. gamma
   0.05 and the 10-minute window are tutorial placeholders.
10. Fills are read from our orders in FILLED status just before clear_inactive_orders; with
    no partial fills that is every fill once.
11. Markouts use the fill's exchange time and the mid recorded at the last 100 ms decision
    step at or before t + h.
12. Quote presence counts a side as quoted while our order there exists, including while a
    cancel is in flight. B0 shows 0.76 because the inventory cap removes one side.
13. Inventory at funding times is reported at 08:00 and 16:00 UTC; 00:00 falls in the
    warm-up.
14. The smoke config's third fee level is the Liquidity Provider Program's Tier 1 maker fee,
    -0.1 bp, which is published (Q6 is still open).
15. AC2.2 and AC2.3 tests were written after the code they check, so they confirm rather
    than drive it.
16. scripts/benchmark_m0.py was updated for the new run_b0 signature but not re-run; its
    figures in data/benchmark_m0.json come from the earlier code, whose decisions are the
    same (the smoke run reproduces its 31,464 fills).
17. Per-step records are not saved to results/, only metrics and fills with markouts.

Proposed checks
18. AC2.4 counts a tie as passing; SPEC.md says "the fewest".
19. AC2.2 reads every run, smoke included.
20. AC1.3 expects "rule N" in EXCLUSIONS.md; AC3.6 asks for a naming convention for the
    oracle's forward arrays (`future_mid`, `forward_*`).

## Open questions

From docs/DATA_RECON.md, still open: Q2 (queue-model variants), Q3 (exchange model, and
the partial-fill panic), Q4 (disk: M1 needs about 26 GB, about 8 GB free), Q5 (the 0.01
grid prints), Q6 (third fee level), Q7 (compute limit), Q8 (B0 at h = 1 quotes one tick
behind the best), Q9 (order size fixed per day), Q10 (canaries in which cells), Q11 (order
latency interpolation and the snapshot sample), Q12 (the Tardis endpoint change on
2026-03-18), Q13 (what to do on a ConversionError), Q15 (minor deferrals), Q16 (download
pacing under the rate limit).

New in this block:
- Q19. Apply the Q14 proposal (docs/proposals/Q14/) and add configs/repo.yaml to the
  protected list?
- Q20. Move tests/pending_leakage/ into tests/leakage/ (AC2.6 and AC3.1 expect them there)?
- Q21. Approve the proposed checks for M1, M2 and M3 (docs/proposals/)?
- Q22. When may downloads resume? The rule in force is no tardis.dev request until you say
  so; the server also asked for none before 2026-10-23 15:26:43 UTC. M1 needs 17 more days.
- Q23. B1's gamma and window, and the B0 h grid, are chosen on all 12 training days in
  M2 (section 4); the smoke values are placeholders only.

# Continued block, 2026-10-23 (items 12 to 17)

Same rules, all kept: no protected path edited (nothing staged under any path in
.claude/protected-paths.txt in commits a90620e to the last commit of this block), no
tardis.dev request (data/tardis_requests.jsonl is still empty), a commit and push after
each item. Every run below is SMOKE on the one training day on disk, 2024-01-01, with
placeholder parameters. Nothing was selected and configs/selected.yaml was not written.

## What was done

| # | Item | Commit | Where |
|---|---|---|---|
| 12 | AC1.2 re-hash test; exclusion rules by script | a90620e | tests/unit/test_raw_hashes.py, data/exclusions.py, docs/data_quality/EXCLUSIONS.md |
| 13a | Overlays B2, B2b, B3 in one loop with B1; normalisers and K | c8fcb96 | strategies/overlay.py, signals/normalise.py |
| 13b | SMOKE Hawkes fit and K on 2024-01-01; overlay grid, 24 cells | bcf355c, 63aea61 | docs/smoke/signals_2024-01-01.json, results/1b171034b708/, docs/smoke/smoke_overlays_2024-01-01.md |
| 14 | Analysis code: bootstrap, t interval, MDE, section 11 statements, selectivity | acd8fc1 | eval/bootstrap.py |
| 15 | Hawkes time-rescaling residuals and KS (AC3.5 tooling) | 2d0d9b3 | signals/hawkes_fit.py, docs/smoke/hawkes_residuals_2024-01-01.json |
| 16 | Canaries C1 to C4 and the AC3.6 test; SMOKE canary run | d9c52bb, 37de49d | tests/canary/, engine/run.py, results/683bdb67ceee/, docs/smoke/smoke_canaries_2024-01-01.md |
| 17 | Parameter selection tool by the section 4 rule | 1e22d7c | eval/select.py, scripts/select_params.py |
| 18 | Leakage audit of the canary run; quote presence fix | 679c894, 37de49d | docs/smoke/audit_canaries_2024-01-01.md, strategies/common.py |

### Highlights by item

12. The AC1.2 test (slow) re-hashes every file in data/raw against data/manifest.json.
    Exclusion rule 1 follows the Q18 wording (a GET that returns 404 or 400 twice, at
    least 24 hours apart); rules 2 and 3 read the data-quality report. No day is
    excluded; 1 of 34 days has been assessed.
13. One numba loop runs B1 (mode NONE) and the three overlays, so B1 and every overlay
    share their quoting code. With c = d = 0 each overlay gives exactly B1's fills, and
    B1 itself is unchanged by the refactor (4,546 fills, -51.0243 USDT gross on
    2024-01-01). The loop's u and m equal the offline signal functions to 1e-9.
    SMOKE Hawkes fit on 2024-01-01: 598,584 events, branching ratio 0.594, beta 7.83 per
    second. SMOKE overlay grid at c = d = 0.5: every cell loses before fees (BEF -0.83 to
    -0.89 bp), and the risk-averse model has the fewest fills in every row, tied with
    power n = 2 for B3 at both latencies. Nothing looked too good, so no audit was
    triggered.
14. The bootstrap uses seed 1729 and 10,000 resamples of days; a day where either
    strategy has no fills is dropped from the pair and listed. If the bootstrap and t
    intervals disagree about 0, the statement is "inconclusive", as section 8 says.
15. In-sample on the fitted day, the rescaled residuals have means 0.999 (buys) and 0.989
    (sells), but KS rejects exponential residuals (statistics 0.073 and 0.070, p about
    0 with about 300,000 residuals each). This fits the known limitation of a constant
    baseline over a whole day. AC3.5 itself is a validation-day check and was not run.
16. C2 builds its forward-looking series only in tests/canary/ and reaches the loop
    through a hook (judgment call 28). SMOKE canary run in the primary cell, plus zero
    latency (BEF in bp, high then zero): B1 -0.874 and -0.869; B3 -0.869 and -0.881;
    C1 -0.894 and -0.893; C2 +0.342 and +0.348; C4 at x10 -0.888 and -0.889; C4 at x0.1
    -0.859 and -0.868. One day gives no interval, so no canary passes or fails here.
    C2 earns spread before fees, as an oracle should, and still loses at the 2.0 bp
    maker fee (-139.9 USDT at high latency).
17. The tool ranks candidates by mean daily BEF in the primary cell and breaks overlay
    ties by the smaller c + d, then the shorter window or decay. A run that does not
    cover exactly the split's non-excluded days, or is labelled smoke, gets a ranking
    headed "SMOKE ranking (chooses nothing)". It refuses to write a file named
    selected.yaml.
18. B3, C4 at x0.1 and C4 at x10 beat their zero-latency twins, so the leakage-auditor
    ran before anything else. Verdict: noise, not leakage or a bug. Latency changes which
    orders fill (about 2,030 of B3's fills are common to both runs), the paired hourly
    bootstrap of B3 high minus zero is +0.0125 bp with interval [-0.014, +0.040], and
    shifting the latency file in time moves B3's BEF across zero's value. Of its six
    findings one was a bug: quote presence was 1.0 by construction, because a step
    counted as quoted whenever the inventory cap allowed both sides. Fixed with a test
    (679c894). It now needs an acknowledged order on each side. Fills, PnL, BEF and
    markouts do not change. On 2024-01-01 in the primary cell, presence is 0.946 for B1
    and 0.416 for B3. The quote presence column in the three committed smoke runs
    predates the fix, and their reports now say so. The other findings are Q25 and
    Q28 to Q30. Judgment call 12 of the earlier block was wrong: B0's 0.76 was the
    share of steps inside the inventory cap.

## Test results

Commands run at the end of this block:

- `make check`: exit 0, 216 passed, 17 deselected (slow).
- AC1.4, AC1.5, AC3.1, AC3.2 and AC3.3 (tests/unit/test_market_orders.py,
  tests/unit/test_hawkes.py, tests/pending_leakage/test_future_perturbation.py, slow
  included): 25 passed.
- `uv run python scripts/check_milestone.py M0`: 21/21, exit 0.
- Slow tests run in this block: the quote-presence test, tests/unit/test_overlay_loop.py
  and tests/unit/test_accounting.py (9 passed), and the C2 loop test in tests/canary/.

## Judgment calls to check

21. The Hawkes fit uses exchange timestamps; the online intensity at decision time uses
    local timestamps, so the strategy sees an event only once it has been received.
22. K is the 99th percentile of a / abar - 1 over the quoting window, abar the trailing
    mean of 18,000 steps (30 minutes). The ring buffer recomputes its sum on every wrap
    so rounding error cannot build up over a day.
23. The SMOKE K values and Hawkes parameters come from 2024-01-01 alone. The study's
    values come from the 12 training days (section 5) and are not computed yet.
24. C1 is one permutation of the day's event sides (seed 1729), fed to B3's fitted
    parameters with no refit. Section 10 does not say how many permutations.
25. C4 keeps B3's K for both decay variants. Recomputing K for each variant on training
    days is the alternative (Q25). On 2024-01-01 the per-variant K would be 7.665 (x10)
    and 2.006 (x0.1), against 3.464 for B3 (from the audit).
26. C2 uses c = 1 and m = 0 with B1's parameters; its u is 0 in the last 5 s of the data,
    where no mid 5 s ahead exists. The oracle reads the mid on the local clock.
27. C3 sets order latency to zero. Feed latency stays, because it is in the data as
    local minus exchange time (Q26).
28. C2 reaches the engine through a hook: run_config takes a callable that returns the
    oracle series, and only tests/canary/run_c2.py passes one. A config with C2 run
    through make run stops before any cell. No file in src builds a forward-looking
    array, which tests/pending_leakage/test_forward_arrays.py checks by name.
29. The results gained a label column, so two entries of one strategy (C4 at x10 and
    x0.1) get separate fills files. Older runs have no such column; the smoke report
    falls back to the strategy name.
30. Selection ties are means within 1e-9 bp. Candidates at c = d = 0 reduce to B1 and tie
    exactly, which is the case the tie rule exists for.
31. Where section 4 has no rule, the selection tool raises instead of choosing: a tie
    between B0 or B1 candidates, a candidate with a day without fills, and an overlay tie
    that c + d and the window do not break (Q27).

## Open questions, new in this block

- Q24. C1: one permutation or several, and should B3 be refit on the shuffled events?
  Taken: one permutation, seed 1729, no refit.
- Q25. C4: keep B3's K or recompute K for each decay variant? Taken: keep B3's K.
- Q26. C3: zero order latency only, or also remove feed latency (local time equal to
  exchange time)? Taken: zero order latency only.
- Q27. Rules for the cases section 4 leaves open: B0 or B1 ties, a candidate with a day
  without fills, overlay ties the rule cannot break. Taken: the tool stops and asks.
- Q28. C1 keeps B3's magnitude m, which does not depend on signs, and section 10 compares
  it with B1. With d > 0, C1 minus B1 can exclude 0 with no sign information at all,
  which would trigger the section 11 statement on C1. Compare C1 with B3 at c = 0
  instead, or set C1's d to 0? This has to be settled before the tag.
- Q29. The C3 flag and the CLAUDE.md zero-latency trigger compare means. On one day the
  noise is as large as the latency effect. Judge C3 with the paired day-level intervals
  used elsewhere?
- Q30. Order latency at t is interpolated between one-second feed-latency rows on both
  sides of t, so it uses feed latency up to 1 s ahead. The strategy cannot read it. State
  it as a limitation, or shift the latency file by one row so it is causal?
- Q31. B3 rests on both sides in 42% of steps against B1's 95%. Corrected on
  2026-10-23: latency is not the cause, since B3 at zero order latency rests 41.6% of
  steps, the same as at high latency (41.6%). place_quotes sends the cancel at one step
  and the replacement only at the next, once the side has no order, so every change of
  target price leaves that side empty for at least one 100 ms step. B3's target moves
  far more often than B1's. That lowers B3's fills and bears on the section 8
  selectivity check. Keep one order per side with cancel first, or allow a replace in
  the same step (the inventory cap then needs in-flight orders counted)?

# Continued again, 2026-10-23 (items 19 to 29)

Same rules, all kept: no protected path edited, no tardis.dev request, a commit and push
after each item. No new data: everything runs on 2024-01-01 or on synthetic tables, and
the pipeline for the steps that need more days is written and tested but not run.

## What was done

| # | Item | Commit |
|---|---|---|
| 19 | Re-ran the three smoke configs so quote presence is valid | ffebfca |
| 20 | Fills sorted by local time and order id before metrics (audit finding 6) | 64fea2b |
| 21 | Pre-registered analysis, eval/analysis.py and scripts/analyse.py | f18d6b4, 6fcd135 |
| 22 | Training-day signal constants, scripts/fit_signals.py | 8013192 |
| 23 | Config builders for every study run; per-strategy cells in the grid | 8b7654b, cee250c |
| 24 | Proposal: canary decisions with exact PREREGISTRATION.md text | b12fae3 |
| 25 | Proposed checks for M4 and M5, with dry run and positive control | 84a94e0 |
| 26 | README: how to reproduce the study (AC6.4) | 654fdb0 |
| 27 | Bound on overfilled fills under the no-partial-fill exchange (Q3) | 644a1ee |
| 28 | Proposal: text for the five M0 [TBD]s in PREREGISTRATION.md | 5bd711b |
| 29 | Independent review of the analysis code; its findings fixed | f1c2f94 |

### Highlights

19. Same configs, same hashes. Fills, notional and the engine's cash and position are
    identical to the first runs; floats derived from them differ by at most 1.6e-12 USDT,
    from fill order. Quote presence in the primary cell: B0 0.71, B1 0.95, B2 0.71,
    B2b 0.69, B3 0.42, C2 0.93.
21. H1 in the primary cell with its sign in all 8 cells, H2 to H4 and markout
    differences labelled exploratory, selectivity, canaries C1 to C4, s and the MDE, and
    the summary the paper template reads (a test checks every template key is there).
    Running it on the smoke results found a bug: with one day the intervals are NaN, and
    NaN read as "excludes 0", so it printed a section 11 statement. Fixed: no conclusion
    and no canary verdict without an interval.
22. It refuses until all 12 training days are on disk. In smoke mode on 2024-01-01 it
    reproduces the earlier fit and K exactly and adds K for every W and tau of the grid
    and for the C4 variants (7.665 and 2.006 against B3's 3.464).
23. Builders for the training, tuning, canary, MDE and confirmatory configs, from
    docs/signals/train_constants.json and configs/selected.yaml (format proposed in
    engine/configs.py). The confirmatory grid is one config (AC5.3): a strategy entry
    can name its own cells, so canaries sit in the primary cell and C3 at zero latency.
    Existing configs expand and hash as before. scripts/make_configs.py never writes
    selected.yaml and never overwrites a config.
25. The checks fail where they should on the repo as it is, and AC4.1 to AC4.3 pass on
    a synthetic temporary root. The M2 proposal was fixed on the way: its m2_runs would
    have overwritten the new strategy label column.
27. On 2024-01-01 in the primary cell, fills where the prints at the order's price total
    less than the order (a lower bound): B0 14 of 28,830, B1 1 of 4,502, B3 0 of 2,556.
    Fills made only by prints at the order's price (the upper bound): 5.2%, 17.4% and
    8.5%. Their 10 s markouts are close to those of fills where the price traded
    through, so there is no sign that they are much less adverse.
29. A reviewer read the analysis, selection and config code against the
    preregistration and found seven issues. Fixed with tests:
    - the paper summary guard trusted any s and any non-smoke run on the test days; it
      now needs configs/runs/confirmatory.yaml as committed, a commit after prereg-v1,
      every label on every test day in each of its cells, and s equal to section 9;
    - a day one side lacked was dropped silently, and a missing cell read as "does not
      hold"; both are now errors;
    - a failed C1 did not stop the H1 statement from interpreting the result;
    - selectivity left out the days B3 did not trade;
    - s could silently be the training estimate alone;
    - the C4 sentence said "both" when it did not know both;
    - the paper called the tag's creation time its push time.
    Left for decisions: Q34 to Q36 below.

## Test results

- `make check`: exit 0, 246 passed, 17 deselected (slow).
- Slow tests run in this stretch: tests/unit/test_accounting.py (3 passed, with the new
  fill-order check), the quote-presence test and the C2 loop test.

## Open questions, new

- Q30 duplicates Q11 in docs/DATA_RECON.md (the order latency look-ahead); docs/ENGINE.md
  already states it. Treat them as one.
- Q32. The configs/selected.yaml format proposed in src/toxic_flow/engine/configs.py.
- Q33. The confirmatory grid as one config with per-strategy cells, and B2b added to the
  validation canary run so s comes from one run per split.
- Q34. C1's pass and C4's match use only the bootstrap interval, which section 8 says is
  too narrow at 16 days. Require both intervals, as H1 does?
- Q35. "Ratio of B3 to B2b traded notional on the median test day": the code takes the
  median of daily ratios, counting days B3 did not trade as 0. Or the ratio of medians?
- Q36. When the two intervals disagree about 0 and |mean| is below the MDE, section 11's
  sentence ("the point estimate is large") is false. The code now says: "Inconclusive:
  the bootstrap and t intervals disagree on whether 0 is inside, and the point estimate
  is below the minimum detectable effect." Accept that wording for section 11?
- Q37. The paper now gives the tag's creation time. The push time is your first entry in
  DEVIATIONS.md; should the paper read it from there?
- Q38. Markouts add the horizon to the fill's exchange time but read the mid on the
  local-time decision grid, so the clocks differ by the feed latency, a few ms. State it,
  or move the lookup onto exchange time?

## Items 30 and 31

| # | Item | Commit |
|---|---|---|
| 30 | Paper figures (per-day D_i, mean D in all 8 cells) and the one-page PDF (AC6.2) | a9a6c5c |
| 31 | Q31 corrected: B3's quote presence is set by cancel-then-replace, not latency | f6e9cb5 |

30. paper/figures.py builds both figures and summary.pdf from results/summary.json only,
    and make paper runs it after the text. matplotlib is now declared in pyproject.toml
    at the version hftbacktest had already locked (3.11.2), so uv.lock gained only the
    direct-dependency entry. Tested on a summary that eval/analysis.py built from a
    synthetic table; no study figure exists yet.

What remains needs the 17 missing training and validation days (Q22) or a decision from
the lists above. In order of what blocks the tag: Q22 (downloads), Q23 (B1 grid), Q28
(C1's comparator), Q25 (C4's K), Q2, Q3 and Q6 (the M0 text in
docs/proposals/prereg_m0_tbds.md), then Q34 to Q36 (analysis wording).

# Block of 2026-10-23 evening: decisions, downloads, M1 to M3

Rules as before: no protected path edited, no test-day URL requested, a commit and push
after each item, no M4 work.

## Decisions applied

- Q31: place_quotes now cancels a stale order and sends its replacement in the same
  100 ms step, for B0 to B3 and every canary alike. The rule is in PREREGISTRATION.md
  section 3. A replacement waits only while an earlier order on that side is
  unacknowledged, or while the inventory cap would not hold with every open order on
  that side filled, cancels in flight included. New test: at zero latency, five ticks
  out, both sides rest in more than 95% of steps (79% with the old rule).
- Q23: B1 grid in PREREGISTRATION.md section 4, committed before any run with it:
  gamma in {0.025, 0.05, 0.1, 0.2} and window in {5, 10, 20} minutes, 12 combinations.
  The GLFT tutorial at py-v2.4.4 has no grid: it uses gamma = 0.05 ("arbitrarily
  chosen") and a 10-minute window, so the grid spans factors of two around both, and
  every window fits inside the 30-minute warm-up. B0 grid h in {1, 2, 3, 5}, as written.
- Q28: C1 stays compared with B1; C1 against B3 is reported beside it as descriptive
  (section 10 and eval/analysis.py).
- Q25: each C4 variant gets its own K from the training days (section 10 and
  engine/configs.py).
- Facts applied from docs/proposals/prereg_m0_tbds.md: the engine version (2.4.4) and
  the latency API with its one-second look-ahead (section 3). Left for you, because each
  is a design choice: the exchange model (Q3), the queue-model variants (Q2), the third
  fee level (Q6), and the analysis wording in Q34 to Q36.

## Item by item

| # | Item | State | Commit |
|---|---|---|---|
| Q31 | Same-step replacement, section 3; smoke grid re-run with presence before and after | done | 7d24a8b, 9cb4bb2 |
| 1 | Download and hash the 17 days | done: 36 files for 18 days in the manifest, with bytes (AC1.6); 68 requests, none to a test-day URL | 86b69b1 |
| 1 | Convert them | not on disk: no room (see Blockers) | |
| 2 | Market-order events for all 18 days | done, from the raw trades with a streamed offset; every offset is 0 | 1c7bdbe |
| 2 | Data-quality files | 3 of 18 days (2024-01-01, 2024-06-01, 2025-01-01) | this commit |
| 2 | Exclusion rules | rule 1 clear on all 18 (every GET returned 200); rules 2 and 3 need the quality files, so 3 of 18 assessed, none excluded | |
| 3 | M2 selection, selected.yaml, chosen B0 and B1 in 8 cells | not started: needs the training days converted (see Blockers) | |
| 4 | M3: pooled Hawkes fit, K, validation diagnostics in docs/hawkes_fit.md | done except B2's K | 8dd2e1c |
| Q13 | Converter refused 2024-02-01 and 2024-03-01; fixed so a larger later snapshot is kept whole | done, unit-tested; not yet run on those two days | f87ca92 |

## Results

Q31, risk-averse cell on 2024-01-01 (docs/smoke/q31_presence_2024-01-01.md): quote
presence rose from 0.416 to 0.995 for B3, 0.710 to 0.994 for B2, 0.690 to 0.995 for B2b
and 0.946 to 0.994 for B1; B0 from 0.709 to 0.727, held by its inventory cap. Fills rose
with it (B3 2,556 to 4,314). Every run now does better at zero latency than at high, and
every break-even fee is negative except the oracle C2 (+0.27 bp, below the 2 bp maker
fee), so no audit was triggered.

M3 (docs/hawkes_fit.md): 11,847,459 events on the 12 training days; branching ratio 0.670,
so AC3.4 holds; beta 13.80 per second. K: B2b 3.450, 2.650 and 2.142 at tau 1, 5 and
30 s; B3 3.878; C4 9.303 (x10) and 2.197 (x0.1). On all 6 validation days the KS test
rejects Exp(1) residuals (statistics 0.050 to 0.152) and the residual mean is 1.02 to
1.34: the training fit expects more events than these days had. The fit values are now
in PREREGISTRATION.md section 5; "Constants K" stays [TBD] until B2's K exists.

Data quality, 3 days: largest gap in the quoting window 9.0 s (trades, 2024-06-01) and
6.9 s (trades, 2025-01-01), below the rule 3 threshold; no crossed or one-sided book
batches. Feed latency p50 of the book 9.1 ms on 2024-06-01 and 2.6 ms on 2025-01-01.

## Blockers

Disk and memory, not code. The raw files for 18 days take 11.2 GB, and with them the
disk has about 0.4 to 3 GB free, varying with swap. macOS swap is 12.5 GB of 13 in use and
lives on the same disk, so every multi-GB job grows swap into the last free space.

- Deleting the derived converted parts of 2024-01-01 to make room was denied by the
  permission check, so nothing under data/ was removed.
- Instead, M1 converts in memory (scripts/prepare_day.py; on 2024-01-01 it reproduces the
  on-disk report, events and OFI file byte for byte). That worked for 2 more days, then
  a watchdog killed 2024-12-01 at 433 MB free, before the disk could fill. An earlier
  run without the watchdog did fill the disk; it was stopped and nothing was lost.
- The engine can also run from memory (day_parts in engine/run.py), but M2 needs 12 such
  conversions per config.
- make check needs 1 GiB free: the downloader's disk guard tests refuse below that. So
  the last files of this block may wait for disk before they can be committed.

What would unblock items 1 to 3, your choice:
- About 15 GB more free disk: convert every train and val day once (make data), then M2
  runs as written.
- Or permission to delete data/converted/<day>/part-*.npz after a day's runs: they are
  derived, and reconversion from the hashed raw files is deterministic (byte-identical
  outputs on 2024-01-01). Then one day at a time fits.
- Either way, closing idle apps would shrink swap and give memory back.

## Judgment calls

- Q23: the GLFT tutorial has no grid, so the grid spans factors of two around its gamma
  (0.05) and window (10 min).
- Q31: a replacement waits while an earlier order on its side is unacknowledged, and the
  cap counts cancels in flight, so in-flight orders cannot breach the cap.
- Q13: when a later snapshot has more levels than an earlier one, the converter keeps it
  whole, departing from hftbacktest's one-shot output, which would cut it short. Both
  alternatives were worse: excluding the day breaks section 2, and copying the cut
  reproduces a library bug.
- Events built from raw trades with a streamed offset equal the converter's; the offset
  was 0 on every day.
- M3 ran without B2's K rather than wait; it is listed as not computed.
- Q2, Q3, Q6, Q34 to Q36 were left open: each involves design (see the decisions above).

## Open questions, new

- Q39. Disk and memory: which of the options under Blockers?
- Q40. Confirm the Q13 converter fix (keep a larger later snapshot whole).

## Second attempt at items 2 and 3 (21:20 to 21:25 UTC)

Disk came back to 2.1 GB while swap shrank, and the waiting files were committed
(303a478). The engine now waits for 1.5 GB of free disk before converting a day in memory
(9ddd074), and scripts/m2_report.py is ready for the AC2.4 table. The M1 loop then waited
for 1.5 GB before each day and ran it under the 700 MB watchdog. The watchdog killed
2024-12-01 twice: swap stayed at 12.1 to 12.2 GB of 12.8 GB with 76% of RAM free, and each
conversion allocated another 1 GB swap file. The loop was stopped. Nothing was lost and
nothing under data/ was removed.

So items 1 (conversion), 2 (15 of 18 quality files) and 3 (all of M2) cannot be done on
this machine as it stands, and repeating the attempt only thrashes it. Q39 holds: about
15 GB more free disk, or permission to delete derived parts after use, or fewer
programs holding swapped-out memory.

## After the reboot (22:20 UTC): disk rules and the stop

The disk filled during an in-memory conversion and the Mac rebooted. Nothing in the repo
was lost (HEAD 7fe58a5, clean tree, git fsck shows only dangling objects). Ilia freed
space (13.4 GB free) and set four rules; all are applied:

1. Measured and written to docs/disk_budget.md.
2. Converted days are a cache (7414650): each part's SHA-256 is in data/manifest.json under
   "converted" and a rebuild must match it; after a day's runs its parts are deleted unless
   more than 30 GB is free; raw files and raw manifest entries are unchanged. The hash is of
   the part's events, not the .npz file, because the zip stores a write time. The hashes of
   2024-01-01 were recorded from its existing parts; its first rebuild will check them.
3. No conversion starts below 15 GB free, one at a time; the in-memory path is gone from the
   engine and from scripts/prepare_day.py.
4. Raw for all 34 days does not fit with 30 GB to spare: about 9.9 GB more raw for the test
   days (4.2 to 16.2 GB, since their sizes cannot be known before the tag) needs about
   39.9 GB free, against 13.4 GB. Short by about 26 GB. Work stops for an external SSD or a
   cloud machine. Rule 3 also blocks M1 and M2 now: 13.4 GB is below the 15 GB floor.

State of the goal: items 1 to 3 remain incomplete, as in the table above. Item 4 is done
except B2's K. No raw file was deleted, no protected path edited, no test-day URL
requested, no M4 work started.
