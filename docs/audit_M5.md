# Leakage audit of the M5 test-day runs (SPEC.md AC5.4)

Auditor: leakage-auditor subagent, 2026-10-30. Read-only: no file edited, no tag touched,
no backtest run. The void folder outside the repository was not opened. The report is kept
as the auditor wrote it, laid out as lists and tables; the response at the end is the main
session's.

Runs audited: results/fb5cb1e00ce5 (configs/runs/confirmatory.yaml, commit 2474a83),
results/5e57ec7d771f (configs/runs/confirmatory_controls.yaml, commit 6a6a096),
results/summary.json (commit b111530). HEAD moved from f4219a5 to 59f3d58 during the audit;
that commit changes only paper/template.md and scripts/site_data.py, no result file.

**Bottom line:** none of the checks changes a pre-registered verdict. Two things change how
the results should be read: what size of effect the study could detect, and the C4 sentence.

## 1. Split discipline and timing

| Check | Command or file | Outcome |
|---|---|---|
| Tag time | `git for-each-ref refs/tags/prereg-v1`, `git cat-file -p prereg-v1` | Tag object 422f3b4 on commit 66c639d, tagger time 2026-10-29T02:38:54Z. |
| Tag on the public remote | `git ls-remote --tags origin` | Lists 422f3b4 and 66c639d for prereg-v1. Pass. |
| Manifest at the tag | `git show prereg-v1:data/manifest.json` | No entry with split "test" and no test date. Pass. |
| Test downloads after the tag | data/manifest.json, data/tardis_requests.jsonl, file birth times | First test-day request 02:56:38Z; all 32 downloaded_at values from 02:57:17Z to 03:14:13Z; birth times match. All after the tag was created (02:38:54Z) and after ls-remote listed it (02:40:37Z). Pass (AC5.1). |
| Exclusions before any result | docs/data_quality/EXCLUSIONS.md, commit c5ae547 (2026-10-29 07:43:49Z) | Before the config (255b523, 07:44:28Z) and the first, void, run (about 07:47Z). No rule met; largest gap 60.4 s, 2026-08-01 book. Pass (AC5.2). |
| Configs committed before their runs | `git log`; meta.json started_at | confirmatory.yaml 2026-10-29T07:44Z, run restarted 2026-10-30T03:03:21Z; controls.yaml 08:21:24Z, run 08:21:46Z. Pass. |
| Config hashes | `toxic_flow.engine.grid.config_hash` on the committed YAML; diff against results/<h>/config.yaml | Both recompute exactly; copies identical. Pass. |
| Code at the run commits equals the tag | `git diff --stat prereg-v1 2474a83` and `prereg-v1 6a6a096` | src/ unchanged. configs/ only adds the two run configs. Other changes: scripts/check_milestone.py (M6 checks), scripts/restore_raw.py, scripts/site_replay.py, two unit tests; none in the engine path. PREREGISTRATION.md, configs/selected.yaml, venue.yaml, splits.yaml, docs/signals, tests/canary and uv.lock byte-identical to the tag. hftbacktest 2.4.4. Pass. |
| The commit made 43 s after the start | `git show --stat 428e842` | Touches only DEVIATIONS.md and docs/void_run_fb5cb1e00ce5.sha256. Pass. |
| Void run had no effect | `shasum -a 256 -c docs/void_run_fb5cb1e00ce5.sha256` inside results/fb5cb1e00ce5 (the restarted run's files) | 451 of 451 OK: the restart reproduced every file the void run wrote, byte for byte, so the void run could not have steered anything. |
| No leftover files | file birth times in results/fb5cb1e00ce5 | All created at or after the restart. 720 fill files, 45 cells x 16 days. Pass. |

## 2. Where thresholds, constants and settings come from

| Check | File | Outcome |
|---|---|---|
| Threshold file | docs/signals/train_thresholds.json | SHA-256 equals section 5's (c9fa1ce1...); `days` lists the 12 training days. |
| Run config against thresholds | configs/runs/confirmatory.yaml | theta_u(p) and theta_m match for B2, B2b, B3, C1, C4_x10, C4_x0.1 and zero-latency B3. K and Hawkes mu, alpha, beta match docs/signals/train_constants.json (12 training days). Pass. |
| Selected settings | configs/selected.yaml; runs 0bd4181a312a, 9e93e4415b6b | Tuning runs use validation days only. The F hold comes from run 83bb2b991997 on training days. Unchanged since 2ae88eb (2026-10-26). Pass. |
| Controls' pull rates from the first run's primary cell | scripts/make_v2_configs.py `realised_rates` | Every R and RL pull_rate equals the toxic_share of C1, B3 or B2b in risk_averse/high; RL episodes equal toxic_episodes there. B3's and B2b's toxic_share is the same in all 8 cells (the signal does not depend on fills or order latency). Realised shares and episode counts 0.996 to 1.001 of target. Pass. |

## 3. Signal causality and layering

| Check | File | Outcome |
|---|---|---|
| Event clock | src/toxic_flow/events/market_orders.py:50 | local_ts is the latest local_timestamp among an event's prints plus the conversion offset; offset 0 on every test day, min(local_ts - exch_ts) 1.3 to 2.1 ms. |
| Signal reads only the past | src/toxic_flow/strategies/signal_input.py:33, 48-50, 60 | Only ts <= now; OFI window (now - W, now]; EXTERNAL returns the last point at or before now. No off-by-one. |
| Normalisers trail | src/toxic_flow/signals/normalise.py | Trailing 18,000 steps, NaN until full, NaN gives m = 0 and u = 0. Magnitude rule off for every selected setting. |
| Warm-up | src/toxic_flow/strategies/touch.py:95 | Signal updates from the start of the data, no orders before 00:30. |
| F hold | touch.py:100-108 | Uses the exchange time of a fill the local side has already received. Causal. |
| Layering | imports in strategies and signals; tests/leakage/test_layering.py | No import of eval, markouts or canary code. Only tests/canary/c2_oracle.py builds the forward series, passed only to C2 (run.py:306-312). |
| Leakage tests | `uv run pytest -q tests/leakage` | 32 passed, 6 skipped (lock tests that skip once the tag is public). |

## 4. summary.json recomputed from metrics.parquet

Every number recomputed independently (own bootstrap, seed 1729, 10,000 resamples; paired t
interval; seed means for R and RL).

| Quantity | Recomputed | summary.json |
|---|---|---|
| H1, B3 - B2b, primary cell | mean -0.007352; bootstrap [-0.028676, 0.019201]; t [-0.034160, 0.019457]; 5 of 16 days above 0 | identical |
| Sign in the 8 cells | all negative, -0.0026 (log/low) to -0.0083 (power3/high) | h1_cells_same_sign = 8 |
| MDE from s = 0.0329 | 0.023043 bp | identical |
| H2, H3, H4, rp, rl, f_b3, c1_r1, c1_b1 | equal to 6 decimals | identical |
| C2 - B1 | +2.3888 bp; threshold 0.0691 | identical |
| Selectivity, median B3/B2b notional | 0.9919 (range 0.88 to 1.24) | identical |
| Zero-fill days | none | none dropped |

## 5. The claim across the grid

All 8 cells reported. H1 is null in every cell; every cell mean is negative and inside the
primary interval. The risk-averse cells give the same answer as the others.

## 6. Canaries (section 10)

- C1: C1 - R1 = +0.0015 bp, bootstrap [-0.0009, 0.0040], includes 0. Pass.
- C2: beat B1 by 2.39 bp, on all 16 days. Pass.
- C3: B3 low minus zero +0.0023 bp [-0.0003, 0.0056]; B3 high minus zero +0.0026 bp
  [-0.0034, 0.0099]. Both below the MDE, both intervals include 0: no flag under the
  revised rule.
- C4: C4_x10 - B3 = -0.0032 [-0.0096, 0.0032], matches B3. C4_x0.1 - B3 = +0.0090
  [0.0032, 0.0152], differs and is better than B3. summary.json prints both.

## 7. Positive net PnL at the standard maker fee

All 976 rows filtered for net_pnl_standard_maker > 0: only C2 (3 days, risk_averse/high).
Every other strategy, B3 at zero latency included, has none in any cell. Mean BEF about
-0.93 to -1.04 bp. Pass.

## 8. Venue facts, order size, accounting

| Check | Outcome |
|---|---|
| Venue values | configs/venue.yaml for the 16 test dates: tick 0.1, lot 0.001, maker 2.0 bp; minimum notional 100 USDT through 2026-04-01, 50 USDT from 2026-05-01. Match docs/venue_sources.json and the tick and lot inferred in each quality report. Cited URLs not fetched. |
| Order size | 0.001 or 0.002 BTC, one size per day; no B1 primary-cell fill below that day's minimum notional. max_inventory_lots = 10 in every row. At most 2 orders on one side (cancel in flight plus replacement). |
| Accounting | Over 976 rows gross equals cash + position x mark_mid within 7e-11; notional equals traded value; engine_fee = 0; net = gross - f x N / 10,000 at all three fees; BEF = 10,000 x G / N; fill counts equal the engine's. |
| From the fill files | Gross, notional and fill count recomputed from all 976 fill files: largest difference 4e-9. |
| End-of-day mark | Mid at the first step at or after 23:59:00 (common.py:119). |

## 9. Fills with no print at our price

No-print share: F 0.070, B3 0.091, B2b 0.135, B1 0.145, R_B3 0.150, RL_B3 0.150. Markouts
recomputed with only fills that had a print: B3 - RL_B3 at 1 s +0.0122 bp [0.0092, 0.0153],
16 of 16 days; B3 - R_B3 +0.0161 bp [0.0131, 0.0193]. B3's lead over the random-pull
controls survives without the no-print fills.

## Findings that would change a conclusion

None. No leak, split breach, config mismatch, accounting error or canary failure. Every
number in results/summary.json recomputes from the committed metrics.parquet files.

## Lesser findings

1. The H1 sentence overstates what the test could detect. It says effects of 0.0230 bp or
   larger, from s = 0.0329 bp; the standard deviation of D on the 16 test days is 0.0503 bp,
   which gives an MDE of 0.0352 bp and power of about 45% at 0.023 bp. Both primary
   intervals reach B3 deficits larger than the stated MDE (bootstrap -0.0287, t -0.0342).
   Affects how the statement reads, not its section 11 row.
2. C4 is half reported in the audit brief: C4_x0.1 did better than B3, interval above 0;
   the paper should say both legs.
3. H2's two intervals disagree: bootstrap [-0.0268, -0.0009] excludes 0, t [-0.0283,
   +0.0007] includes it. The paper printed only the bootstrap interval; by section 8 the
   result is inconclusive.
4. C3 is checked in 2 of 8 cells (zero latency runs only under risk_averse, as section 10
   says). In both, the non-zero-latency runs beat zero latency on the mean, 9 of 16 days
   each; zero latency is not acting as an upper bound here, though it does not flag.
5. No-print share differs by strategy (B3 0.091, B2b 0.135); reported per day as section 3
   requires; item 9 shows it does not drive B3's lead over R and RL.
6. Small notes: fills in the 1 s cancel window after 23:59:00 are marked at the 23:59:00
   mid; DEVIATIONS.md entry 4's 05:49 against 06:01:01 EDT is cleared by the identical
   hashes; entry 1 does not list 2474a83 (M6 checks only, no engine code).

## Response (main session, 2026-10-30)

No conclusion changes, so no rerun. Checked by hand: the SD of
summary.json h1.primary.per_day is 0.050310 bp, MDE at that SD 0.035237 bp, power at
0.023043 bp 0.449.

1. Paper: a limitation sentence after the H1 statement says the daily difference varied
   more on the test days than s, so power at the MDE was below 80% and both intervals reach
   deficits larger than the MDE. The section 11 sentence is printed word for word as
   committed; the realised SD is not added as a number, since it is not a key of
   summary.json and adding one means changing src/toxic_flow/eval after the tag. Left for
   Ilia: [TBD: add the test-day SD of D and the MDE at it to summary.json as a deviation?]
2. No change: the paper's canary paragraph prints the full statement from summary.json,
   which names both C4 legs.
3. Paper: the H2 clause now says its paired t interval includes 0, so by section 8 it is
   inconclusive.
4. No change: reported as found; section 10 runs zero latency under risk_averse only.
5. and 6. No change.
