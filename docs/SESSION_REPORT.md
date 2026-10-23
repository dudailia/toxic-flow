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
