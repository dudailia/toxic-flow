# M4 v2: overlay tuning, canaries and MDE (draft for Ilia's review)

Draft for Ilia's review. After C1 passed the revised rule, the selection was copied into
configs/selected.yaml and the [TBD] items of PREREGISTRATION.md were filled from the runs
named here (2026-10-26). All numbers come from the runs named below, through
scripts/m4_v2.py. Training and validation days only; no test day was loaded.

Reading (written by hand from the tables below):
- AC4.2: the v2 oracle C2 beats B1 by 2.10 bp a day (bootstrap [1.92, 2.30], 6 of 6 days),
  far above 3 x MDE (0.069 bp). The harness turns information into PnL on this base.
  C2's own mean BEF is +1.16 bp, below the 2 bp standard maker fee.
- AC4.3 as first written fails narrowly: C1 - B1 = -0.009 bp (bootstrap [-0.013, -0.006],
  0 of 6 days above 0). The leakage audit found no leak and a mechanism: shuffling removes
  the runs of same-side market orders, so C1 marks a side toxic on 1.3% of steps against
  B3's 4.1% with the same threshold, and a pulled quote rejoins at the back of the queue,
  so pulling costs something even without information. On 2026-10-26 Ilia revised the
  rule (Q53, PREREGISTRATION.md Design history): C1 is judged against R1, B1 that pulls a
  random side at C1's realised rate on each day, 3 seeds. That result is in the section
  "Random-pull controls" below; both are reported.
- AC4.3 as revised passes: C1 - R1 = +0.0009 bp (bootstrap [-0.0023, 0.0038], t
  [-0.0036, 0.0053], 3 of 6 days above 0), and each seed alone also includes 0. R1 loses
  0.0099 bp a day to B1 (bootstrap [-0.0119, -0.0079]), about what C1 loses, so random
  pulls at C1's rate account for C1's gap to B1. C1 and R1 also pull in similar runs
  (438 and 459 runs of one toxic side an hour).
- Exploratory, not tests: B3 beats random pulls at its own rate by 0.028 bp (bootstrap
  [0.023, 0.035], 6 of 6 days) and B2b beats its own by 0.062 bp ([0.030, 0.101], 6 of
  6). These overstate what the signals add, because the random controls pull in shorter
  runs, so they give up queue place more often: R_B3 starts 1,452 runs an hour against
  B3's 1,094, and R_B2b 8,017 against B2b's 338. A control matched on run length as well
  was not run. At matched p (K pull, magnitude off, B2b at tau 5 s), B3 - B2b is -0.001 bp
  at p 5% (interval includes 0) and negative beyond it (-0.027, -0.063 and -0.078 bp at
  10%, 25% and 50%; the bootstrap interval excludes 0 at all three, the t interval at 10%
  and 25% only), so the fitted Hawkes signal
  did no better than the decay-weighted count at any matched pull rate on these days. B3
  marks in shorter runs and so cancels more often (2,529 against 2,090 an hour at 5%, 8,809
  against 1,992 at 50%), so part of that deficit may be the cost of re-queuing rather than
  worse information.
- A leakage audit of the random-pull run (2026-10-26) found no leak and reproduced every
  number above from metrics.parquet: R reads no market data, its series gives exactly one
  point per engine step (the count of pulled runs matches independent draws to 0.2%), and
  B1, C1, B3 and B2b equal the canary run. It ranked the run-length mismatch first; the
  limitation is now printed next to both exploratory tables.
- Q52: C4 at beta x 10 marks 46.0% of training-day steps at p = 50%, not 50%, because its
  intensity returns to baseline between events and |u| ties there. B3 was selected at
  p = 5%, so C4 runs at p = 5% and the tie at 50% affects no result.
- C4: the slower wrong decay (beta x 0.1) beat B3, +0.0086 bp (bootstrap [0.0021,
  0.0154], 5 of 6 days), with B3's p and K chosen on these same days; the faster one
  (x 10) did worse. The generated text says only "differed".
- C3: on the mean, zero latency is above high latency (-0.9365 against -0.9385 bp), but
  per day the high-latency run is above its zero-latency twin on 2 of 6 days
  (2025-03-01, 2025-06-01). Zero latency removes order latency only; the signal runs on
  local timestamps either way.
- Effects are small: the selected overlays move the mean daily BEF by 0.004 (B3) and
  0.010 bp (B2b) against B1, and H1's statistic on validation days is -0.005 bp, against
  an MDE of 0.023 bp on 16 days.
- A failed canary triggers the leakage-auditor (CLAUDE.md). It found no leak: C2's look-ahead
  stays in tests/canary/, the loop reads the series only at points at or before now, the
  thresholds come from training days only, and the accounting reconciles with the engine.

## B0 and B1 on the training days, all 8 cells (section 4, v2)

Run 4db60c584c71 (configs/runs/v2_train.yaml, commit 954c0c8), 12 training days. Means over days; markouts per fill in our favour.

| Strategy | Queue model | Latency | Fills a day | Mean daily BEF bp | Pooled BEF bp | Markout 1 s bp | Markout 60 s bp | Both sides resting |
|---|---|---|---|---|---|---|---|---|
| B0 | risk_averse | low | 70326 | -0.8837 | -0.8916 | -0.6773 | -0.8951 | 0.627 |
| B0 | risk_averse | high | 62997 | -0.8767 | -0.8866 | -0.6643 | -0.8888 | 0.643 |
| B0 | power3 | low | 74354 | -0.8564 | -0.8645 | -0.6470 | -0.8640 | 0.626 |
| B0 | power3 | high | 66908 | -0.8464 | -0.8562 | -0.6319 | -0.8563 | 0.641 |
| B0 | power2 | low | 74481 | -0.8534 | -0.8622 | -0.6445 | -0.8607 | 0.626 |
| B0 | power2 | high | 67040 | -0.8432 | -0.8537 | -0.6294 | -0.8523 | 0.641 |
| B0 | log | low | 78776 | -0.8143 | -0.8268 | -0.6104 | -0.8176 | 0.620 |
| B0 | log | high | 71193 | -0.8040 | -0.8172 | -0.5945 | -0.8087 | 0.634 |
| B1 | risk_averse | low | 66150 | -0.9360 | -0.9419 | -0.7243 | -0.9465 | 0.759 |
| B1 | risk_averse | high | 58978 | -0.9327 | -0.9417 | -0.7165 | -0.9431 | 0.775 |
| B1 | power3 | low | 68939 | -0.9173 | -0.9235 | -0.7049 | -0.9262 | 0.773 |
| B1 | power3 | high | 61679 | -0.9125 | -0.9218 | -0.6957 | -0.9217 | 0.788 |
| B1 | power2 | low | 69001 | -0.9159 | -0.9223 | -0.7033 | -0.9246 | 0.773 |
| B1 | power2 | high | 61737 | -0.9115 | -0.9206 | -0.6942 | -0.9201 | 0.789 |
| B1 | log | low | 71733 | -0.8907 | -0.8998 | -0.6815 | -0.8977 | 0.784 |
| B1 | log | high | 64386 | -0.8855 | -0.8969 | -0.6712 | -0.8931 | 0.799 |

## Thresholds from the training days (section 5, v2)

docs/signals/train_thresholds.json (scripts/fit_thresholds.py). Pooled share of training-day
steps above each threshold in brackets.

| Signal setting | theta_u at p 5% | 10% | 25% | 50% | theta_m |
|---|---|---|---|---|---|
| B2_ofi_1s | 0.9764 (0.050) | 0.9107 (0.100) | 0.5848 (0.250) | 0.1768 (0.500) | 0.2477 (0.100) |
| B2_ofi_5s | 0.9749 (0.050) | 0.9282 (0.100) | 0.7320 (0.250) | 0.3722 (0.500) | 0.3190 (0.100) |
| B2_ofi_30s | 0.9732 (0.050) | 0.9339 (0.100) | 0.7875 (0.250) | 0.5082 (0.500) | 0.3632 (0.100) |
| B2b_ewma_1s | 0.8562 (0.050) | 0.7561 (0.100) | 0.5614 (0.250) | 0.3415 (0.500) | 0.2401 (0.100) |
| B2b_ewma_5s | 0.6463 (0.050) | 0.5597 (0.100) | 0.4045 (0.250) | 0.2398 (0.500) | 0.2482 (0.100) |
| B2b_ewma_30s | 0.4801 (0.050) | 0.3958 (0.100) | 0.2718 (0.250) | 0.1569 (0.500) | 0.2542 (0.100) |
| B3_hawkes | 0.5693 (0.050) | 0.5142 (0.100) | 0.3901 (0.250) | 0.1851 (0.500) | 0.2184 (0.100) |
| C4_x10 | 0.6897 (0.050) | 0.6014 (0.100) | 0.0933 (0.250) | 0.0232 (0.460) | 0.0992 (0.100) |
| C4_x0.1 | 0.3932 (0.050) | 0.3308 (0.100) | 0.2325 (0.250) | 0.1367 (0.500) | 0.2308 (0.100) |

## Overlay tuning on the validation days (section 4, v2)

Runs 0bd4181a312a (configs/runs/v2_tune_val_a.yaml, commit 1e68ba9), 9e93e4415b6b (configs/runs/v2_tune_val_b.yaml, commit 3ad5270), primary cell risk_averse / high, 6 days: 2025-01-01, 2025-02-01, 2025-03-01, 2025-04-01, 2025-05-01, 2025-06-01. Rule: highest mean daily break-even fee; ties to the smaller p, then K (1, 5, pull), then the magnitude rule off, then the shorter window or decay. Toxic share: the realised share of quoting steps with a side marked toxic on these days, against p from the training days.

### B2

| Candidate | Mean daily BEF bp | Pooled BEF bp | Median daily fills | Markout 1 s bp | Toxic share | Days without fills |
|---|---|---|---|---|---|---|
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 5.0} | -0.9341 | -0.9300 | 25670 | -0.7199 | 0.230 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 5.0} | -0.9356 | -0.9310 | 25635 | -0.7208 | 0.230 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 5.0} | -0.9363 | -0.9304 | 32050 | -0.7073 | 0.052 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 5.0} | -0.9376 | -0.9315 | 30577 | -0.7104 | 0.099 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 5.0} | -0.9376 | -0.9315 | 31992 | -0.7086 | 0.052 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 1.0} | -0.9381 | -0.9335 | 27396 | -0.7185 | 0.092 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 5.0} | -0.9385 | -0.9322 | 30543 | -0.7114 | 0.099 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 1.0} | -0.9389 | -0.9319 | 30120 | -0.7125 | 0.051 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 1.0} | -0.9396 | -0.9345 | 27354 | -0.7202 | 0.092 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 1.0} | -0.9411 | -0.9339 | 30028 | -0.7144 | 0.051 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 30.0} | -0.9417 | -0.9346 | 32972 | -0.7057 | 0.051 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "ofi_window_s": 30.0} | -0.9421 | -0.9324 | 33647 | -0.7062 | 0.100 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "ofi_window_s": 30.0} | -0.9421 | -0.9323 | 33671 | -0.7060 | 0.100 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 30.0} | -0.9421 | -0.9349 | 32948 | -0.7062 | 0.051 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "ofi_window_s": 30.0} | -0.9427 | -0.9329 | 33735 | -0.7063 | 0.051 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "ofi_window_s": 30.0} | -0.9427 | -0.9329 | 33708 | -0.7062 | 0.051 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "ofi_window_s": 30.0} | -0.9427 | -0.9332 | 33695 | -0.7067 | 0.100 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "ofi_window_s": 30.0} | -0.9428 | -0.9332 | 33701 | -0.7068 | 0.051 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "ofi_window_s": 30.0} | -0.9429 | -0.9332 | 33676 | -0.7066 | 0.051 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "ofi_window_s": 30.0} | -0.9430 | -0.9331 | 33721 | -0.7065 | 0.100 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 30.0} | -0.9430 | -0.9372 | 28724 | -0.7074 | 0.245 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "ofi_window_s": 30.0} | -0.9430 | -0.9327 | 33426 | -0.7068 | 0.245 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "ofi_window_s": 5.0} | -0.9430 | -0.9330 | 33572 | -0.7074 | 0.052 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "ofi_window_s": 30.0} | -0.9431 | -0.9335 | 33638 | -0.7070 | 0.245 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "ofi_window_s": 30.0} | -0.9433 | -0.9329 | 33442 | -0.7066 | 0.245 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "ofi_window_s": 30.0} | -0.9433 | -0.9333 | 33666 | -0.7068 | 0.245 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 30.0} | -0.9434 | -0.9377 | 32158 | -0.7053 | 0.100 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "ofi_window_s": 30.0} | -0.9434 | -0.9337 | 33526 | -0.7081 | 0.486 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "ofi_window_s": 5.0} | -0.9435 | -0.9333 | 33705 | -0.7067 | 0.052 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 30.0} | -0.9435 | -0.9378 | 28708 | -0.7078 | 0.245 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 30.0} | -0.9436 | -0.9377 | 32138 | -0.7059 | 0.100 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "ofi_window_s": 30.0} | -0.9436 | -0.9335 | 33550 | -0.7079 | 0.486 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "ofi_window_s": 5.0} | -0.9441 | -0.9342 | 33669 | -0.7070 | 0.099 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "ofi_window_s": 1.0} | -0.9442 | -0.9340 | 33667 | -0.7070 | 0.051 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "ofi_window_s": 30.0} | -0.9445 | -0.9334 | 32934 | -0.7095 | 0.486 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "ofi_window_s": 5.0} | -0.9446 | -0.9342 | 33478 | -0.7082 | 0.052 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "ofi_window_s": 5.0} | -0.9446 | -0.9340 | 33621 | -0.7077 | 0.052 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "ofi_window_s": 1.0} | -0.9449 | -0.9343 | 33344 | -0.7090 | 0.051 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "ofi_window_s": 30.0} | -0.9451 | -0.9339 | 32948 | -0.7094 | 0.486 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "ofi_window_s": 5.0} | -0.9451 | -0.9344 | 33581 | -0.7079 | 0.099 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "ofi_window_s": 5.0} | -0.9451 | -0.9344 | 33396 | -0.7089 | 0.099 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "ofi_window_s": 1.0} | -0.9452 | -0.9350 | 33621 | -0.7078 | 0.092 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "ofi_window_s": 5.0} | -0.9454 | -0.9351 | 33569 | -0.7083 | 0.230 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "ofi_window_s": 1.0} | -0.9458 | -0.9356 | 33526 | -0.7089 | 0.209 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "ofi_window_s": 5.0} | -0.9462 | -0.9353 | 33471 | -0.7091 | 0.230 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "ofi_window_s": 5.0} | -0.9462 | -0.9349 | 33298 | -0.7094 | 0.099 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 1.0} | -0.9463 | -0.9504 | 20866 | -0.7342 | 0.209 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "ofi_window_s": 1.0} | -0.9464 | -0.9354 | 33512 | -0.7092 | 0.051 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 30.0} | -0.9468 | -0.9430 | 22485 | -0.7134 | 0.486 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "ofi_window_s": 5.0} | -0.9472 | -0.9359 | 32842 | -0.7134 | 0.230 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "ofi_window_s": 5.0} | -0.9472 | -0.9370 | 33413 | -0.7102 | 0.450 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 30.0} | -0.9474 | -0.9440 | 22475 | -0.7141 | 0.486 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "ofi_window_s": 1.0} | -0.9476 | -0.9366 | 33179 | -0.7113 | 0.051 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "ofi_window_s": 1.0} | -0.9477 | -0.9366 | 33450 | -0.7099 | 0.092 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "ofi_window_s": 1.0} | -0.9481 | -0.9379 | 33051 | -0.7117 | 0.092 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "ofi_window_s": 5.0} | -0.9483 | -0.9365 | 32752 | -0.7139 | 0.230 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "ofi_window_s": 1.0} | -0.9485 | -0.9382 | 33384 | -0.7121 | 0.439 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "ofi_window_s": 5.0} | -0.9487 | -0.9379 | 33314 | -0.7112 | 0.450 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 1.0} | -0.9491 | -0.9523 | 20824 | -0.7357 | 0.209 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "ofi_window_s": 1.0} | -0.9492 | -0.9384 | 33332 | -0.7109 | 0.209 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "ofi_window_s": 1.0} | -0.9495 | -0.9386 | 32862 | -0.7135 | 0.092 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "ofi_window_s": 1.0} | -0.9515 | -0.9405 | 33196 | -0.7142 | 0.439 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "ofi_window_s": 1.0} | -0.9547 | -0.9436 | 32379 | -0.7177 | 0.209 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "ofi_window_s": 1.0} | -0.9566 | -0.9450 | 32225 | -0.7193 | 0.209 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "ofi_window_s": 5.0} | -0.9570 | -0.9452 | 32013 | -0.7205 | 0.450 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 1.0} | -0.9574 | -0.9660 | 13832 | -0.7610 | 0.439 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 5.0} | -0.9581 | -0.9544 | 17963 | -0.7400 | 0.450 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 5.0} | -0.9587 | -0.9553 | 17934 | -0.7413 | 0.450 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "ofi_window_s": 1.0} | -0.9587 | -0.9666 | 13808 | -0.7636 | 0.439 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "ofi_window_s": 5.0} | -0.9588 | -0.9463 | 31922 | -0.7210 | 0.450 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "ofi_window_s": 1.0} | -0.9648 | -0.9536 | 31624 | -0.7279 | 0.439 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "ofi_window_s": 1.0} | -0.9665 | -0.9550 | 31483 | -0.7290 | 0.439 | 0 |

Choice: {"p": 0.25, "k_ticks": "pull", "magnitude": false, "ofi_window_s": 5.0}, mean daily BEF -0.9341 bp.

### B2b

| Candidate | Mean daily BEF bp | Pooled BEF bp | Median daily fills | Markout 1 s bp | Toxic share | Days without fills |
|---|---|---|---|---|---|---|
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "tau_s": 5.0} | -0.9330 | -0.9290 | 27634 | -0.7129 | 0.256 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "tau_s": 5.0} | -0.9331 | -0.9250 | 31752 | -0.7060 | 0.095 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "tau_s": 5.0} | -0.9358 | -0.9276 | 31552 | -0.7090 | 0.095 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "tau_s": 5.0} | -0.9366 | -0.9319 | 27456 | -0.7157 | 0.256 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "tau_s": 1.0} | -0.9375 | -0.9276 | 30782 | -0.7099 | 0.102 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "tau_s": 5.0} | -0.9375 | -0.9294 | 32832 | -0.7059 | 0.042 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "tau_s": 1.0} | -0.9388 | -0.9302 | 25664 | -0.7203 | 0.261 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "tau_s": 1.0} | -0.9391 | -0.9310 | 32471 | -0.7065 | 0.048 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "tau_s": 5.0} | -0.9405 | -0.9320 | 32634 | -0.7088 | 0.042 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": false, "tau_s": 30.0} | -0.9415 | -0.9387 | 27688 | -0.7120 | 0.279 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "tau_s": 1.0} | -0.9420 | -0.9316 | 30567 | -0.7132 | 0.102 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "tau_s": 5.0} | -0.9428 | -0.9328 | 33558 | -0.7074 | 0.095 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "tau_s": 30.0} | -0.9428 | -0.9330 | 33693 | -0.7064 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "tau_s": 5.0} | -0.9428 | -0.9329 | 33650 | -0.7067 | 0.042 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "tau_s": 30.0} | -0.9428 | -0.9330 | 33728 | -0.7064 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "tau_s": 1.0} | -0.9431 | -0.9340 | 32266 | -0.7096 | 0.048 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "tau_s": 5.0} | -0.9432 | -0.9332 | 33716 | -0.7067 | 0.042 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "tau_s": 5.0} | -0.9433 | -0.9332 | 33695 | -0.7069 | 0.095 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "tau_s": 30.0} | -0.9433 | -0.9334 | 33622 | -0.7066 | 0.102 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "tau_s": 30.0} | -0.9435 | -0.9335 | 33710 | -0.7065 | 0.102 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false, "tau_s": 1.0} | -0.9435 | -0.9335 | 33692 | -0.7072 | 0.048 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "tau_s": 30.0} | -0.9438 | -0.9339 | 33346 | -0.7079 | 0.279 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false, "tau_s": 1.0} | -0.9439 | -0.9340 | 33567 | -0.7086 | 0.048 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "tau_s": 1.0} | -0.9444 | -0.9355 | 25460 | -0.7243 | 0.261 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "tau_s": 30.0} | -0.9445 | -0.9343 | 33640 | -0.7071 | 0.279 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true, "tau_s": 30.0} | -0.9446 | -0.9415 | 27546 | -0.7143 | 0.279 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false, "tau_s": 1.0} | -0.9447 | -0.9344 | 33668 | -0.7078 | 0.102 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "tau_s": 5.0} | -0.9448 | -0.9345 | 33632 | -0.7078 | 0.256 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "tau_s": 30.0} | -0.9451 | -0.9351 | 33556 | -0.7084 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "tau_s": 30.0} | -0.9453 | -0.9354 | 33523 | -0.7085 | 0.041 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "tau_s": 5.0} | -0.9455 | -0.9352 | 33371 | -0.7097 | 0.095 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": false, "tau_s": 30.0} | -0.9455 | -0.9364 | 33124 | -0.7069 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "tau_s": 5.0} | -0.9456 | -0.9355 | 33458 | -0.7091 | 0.042 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "tau_s": 30.0} | -0.9456 | -0.9349 | 33544 | -0.7081 | 0.535 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "tau_s": 30.0} | -0.9457 | -0.9356 | 33451 | -0.7087 | 0.102 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "tau_s": 30.0} | -0.9457 | -0.9356 | 33533 | -0.7085 | 0.102 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "tau_s": 5.0} | -0.9457 | -0.9353 | 33523 | -0.7089 | 0.042 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "tau_s": 5.0} | -0.9457 | -0.9353 | 33509 | -0.7090 | 0.095 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false, "tau_s": 1.0} | -0.9457 | -0.9354 | 33397 | -0.7107 | 0.102 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "tau_s": 5.0} | -0.9459 | -0.9350 | 33220 | -0.7105 | 0.256 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "tau_s": 30.0} | -0.9462 | -0.9362 | 33188 | -0.7098 | 0.279 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false, "tau_s": 30.0} | -0.9463 | -0.9388 | 31961 | -0.7078 | 0.102 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false, "tau_s": 1.0} | -0.9464 | -0.9358 | 33564 | -0.7092 | 0.261 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "tau_s": 5.0} | -0.9466 | -0.9358 | 33510 | -0.7091 | 0.517 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "tau_s": 30.0} | -0.9467 | -0.9364 | 33467 | -0.7091 | 0.279 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "tau_s": 5.0} | -0.9474 | -0.9366 | 33438 | -0.7098 | 0.256 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true, "tau_s": 1.0} | -0.9475 | -0.9364 | 33499 | -0.7099 | 0.048 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true, "tau_s": 30.0} | -0.9480 | -0.9387 | 32961 | -0.7090 | 0.041 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "tau_s": 5.0} | -0.9480 | -0.9370 | 33048 | -0.7125 | 0.256 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true, "tau_s": 1.0} | -0.9482 | -0.9372 | 33356 | -0.7113 | 0.048 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "tau_s": 30.0} | -0.9482 | -0.9373 | 33367 | -0.7104 | 0.535 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true, "tau_s": 30.0} | -0.9484 | -0.9409 | 31797 | -0.7098 | 0.102 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true, "tau_s": 1.0} | -0.9484 | -0.9371 | 33470 | -0.7103 | 0.102 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false, "tau_s": 1.0} | -0.9490 | -0.9373 | 33438 | -0.7116 | 0.516 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "tau_s": 5.0} | -0.9491 | -0.9377 | 33326 | -0.7114 | 0.517 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "tau_s": 30.0} | -0.9500 | -0.9386 | 32854 | -0.7115 | 0.535 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true, "tau_s": 1.0} | -0.9501 | -0.9385 | 33182 | -0.7133 | 0.102 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true, "tau_s": 1.0} | -0.9505 | -0.9384 | 33360 | -0.7117 | 0.261 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "tau_s": 5.0} | -0.9506 | -0.9392 | 32624 | -0.7152 | 0.517 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "tau_s": 30.0} | -0.9514 | -0.9402 | 32710 | -0.7134 | 0.535 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false, "tau_s": 1.0} | -0.9515 | -0.9398 | 32856 | -0.7158 | 0.261 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "tau_s": 5.0} | -0.9520 | -0.9405 | 32481 | -0.7169 | 0.517 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "tau_s": 5.0} | -0.9523 | -0.9537 | 19912 | -0.7289 | 0.517 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true, "tau_s": 1.0} | -0.9530 | -0.9401 | 33236 | -0.7142 | 0.516 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "tau_s": 5.0} | -0.9543 | -0.9561 | 19822 | -0.7317 | 0.517 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true, "tau_s": 1.0} | -0.9555 | -0.9427 | 32652 | -0.7184 | 0.261 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false, "tau_s": 1.0} | -0.9604 | -0.9466 | 32122 | -0.7234 | 0.516 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true, "tau_s": 1.0} | -0.9622 | -0.9487 | 31946 | -0.7254 | 0.516 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "tau_s": 30.0} | -0.9661 | -0.9616 | 19962 | -0.7210 | 0.535 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "tau_s": 30.0} | -0.9684 | -0.9641 | 19876 | -0.7231 | 0.535 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false, "tau_s": 1.0} | -0.9799 | -0.9818 | 17800 | -0.7411 | 0.516 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true, "tau_s": 1.0} | -0.9852 | -0.9852 | 17683 | -0.7456 | 0.516 | 0 |

Choice: {"p": 0.25, "k_ticks": "pull", "magnitude": false, "tau_s": 5.0}, mean daily BEF -0.9330 bp.

### B3

| Candidate | Mean daily BEF bp | Pooled BEF bp | Median daily fills | Markout 1 s bp | Toxic share | Days without fills |
|---|---|---|---|---|---|---|
| {"p": 0.05, "k_ticks": "pull", "magnitude": false} | -0.9385 | -0.9299 | 27720 | -0.7015 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": false} | -0.9446 | -0.9344 | 33740 | -0.7078 | 0.041 | 0 |
| {"p": 0.05, "k_ticks": "pull", "magnitude": true} | -0.9465 | -0.9360 | 27558 | -0.7077 | 0.041 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": false} | -0.9478 | -0.9367 | 33702 | -0.7101 | 0.087 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": false} | -0.9488 | -0.9383 | 33310 | -0.7111 | 0.041 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": false} | -0.9504 | -0.9397 | 33598 | -0.7127 | 0.228 | 0 |
| {"p": 0.05, "k_ticks": 1, "magnitude": true} | -0.9522 | -0.9405 | 33494 | -0.7128 | 0.041 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": false} | -0.9527 | -0.9420 | 33450 | -0.7146 | 0.464 | 0 |
| {"p": 0.1, "k_ticks": 1, "magnitude": true} | -0.9529 | -0.9414 | 33478 | -0.7144 | 0.087 | 0 |
| {"p": 0.25, "k_ticks": 1, "magnitude": true} | -0.9556 | -0.9436 | 33386 | -0.7166 | 0.228 | 0 |
| {"p": 0.05, "k_ticks": 5, "magnitude": true} | -0.9563 | -0.9439 | 33060 | -0.7161 | 0.041 | 0 |
| {"p": 0.5, "k_ticks": 1, "magnitude": true} | -0.9569 | -0.9458 | 33278 | -0.7182 | 0.464 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": false} | -0.9574 | -0.9457 | 32888 | -0.7192 | 0.087 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": false} | -0.9604 | -0.9524 | 25266 | -0.7170 | 0.087 | 0 |
| {"p": 0.1, "k_ticks": 5, "magnitude": true} | -0.9620 | -0.9488 | 32664 | -0.7229 | 0.087 | 0 |
| {"p": 0.1, "k_ticks": "pull", "magnitude": true} | -0.9652 | -0.9565 | 25132 | -0.7216 | 0.087 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": false} | -0.9698 | -0.9565 | 32201 | -0.7294 | 0.228 | 0 |
| {"p": 0.25, "k_ticks": 5, "magnitude": true} | -0.9725 | -0.9582 | 32039 | -0.7327 | 0.228 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": false} | -0.9736 | -0.9605 | 31718 | -0.7346 | 0.464 | 0 |
| {"p": 0.5, "k_ticks": 5, "magnitude": true} | -0.9767 | -0.9634 | 31560 | -0.7376 | 0.464 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": false} | -0.9958 | -0.9902 | 20528 | -0.7428 | 0.228 | 0 |
| {"p": 0.25, "k_ticks": "pull", "magnitude": true} | -0.9989 | -0.9927 | 20440 | -0.7475 | 0.228 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": false} | -1.0304 | -1.0392 | 15074 | -0.7607 | 0.464 | 0 |
| {"p": 0.5, "k_ticks": "pull", "magnitude": true} | -1.0366 | -1.0447 | 15014 | -0.7639 | 0.464 | 0 |

Choice: {"p": 0.05, "k_ticks": "pull", "magnitude": false}, mean daily BEF -0.9385 bp.

## Minimum detectable effect (section 9)

s is the larger of the standard deviations of D_i = BEF_B3 - BEF_B2b with the selected
settings: on the training days (run 58c46cc49981) and on the validation days
(run 5d27bc8ae820). n = 16 test days.

| Quantity | Value |
|---|---|
| s on training days, bp | 0.0329 |
| s on validation days, bp | 0.0313 |
| s, bp | 0.0329 |
| MDE = 0.70 s, bp | 0.0231 |
| 3 x MDE (C2 threshold), bp | 0.0692 |

## Canaries on the validation days (section 10, v2)

Run 5d27bc8ae820 (configs/runs/v2_canaries_val.yaml, commit 0fe9f4b), primary cell;
C3 is B3 at zero latency in the risk-averse queue model.

| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |
|---|---|---|---|---|---|---|
| C1 - B1 (pass: interval includes 0) | 6 | -0.0090 | [-0.0126, -0.0055] | [-0.0142, -0.0038] | 0 | none |
| C1 - B3 (descriptive) | 6 | -0.0134 | [-0.0214, -0.0070] | [-0.0237, -0.0031] | 0 | none |
| C2 - B1 (pass: mean above 3 x MDE) | 6 | 2.1018 | [1.9222, 2.2952] | [1.8279, 2.3757] | 6 | none |
| C4_x0.1 - B3 | 6 | 0.0086 | [0.0021, 0.0154] | [-0.0005, 0.0176] | 5 | none |
| C4_x10 - B3 | 6 | -0.0131 | [-0.0209, -0.0070] | [-0.0231, -0.0030] | 0 | none |
| B3 - B1 (descriptive, H3 on validation days) | 6 | 0.0044 | [-0.0037, 0.0136] | [-0.0081, 0.0169] | 4 | none |
| B2b - B1 (descriptive, H4 on validation days) | 6 | 0.0098 | [-0.0075, 0.0293] | [-0.0167, 0.0364] | 4 | none |
| B3 - B2b (descriptive, H1's statistic on validation days) | 6 | -0.0054 | [-0.0302, 0.0163] | [-0.0383, 0.0275] | 2 | none |

| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Toxic share |
|---|---|---|---|---|
| B1 | 39004 | -0.9429 | -0.7063 | 0.000 |
| B2b | 32597 | -0.9330 | -0.7129 | 0.256 |
| B3 | 31958 | -0.9385 | -0.7015 | 0.041 |
| C1 | 38095 | -0.9519 | -0.7133 | 0.013 |
| C2 | 11038 | 1.1589 | -0.2238 | 0.593 |
| C4_x10 | 34098 | -0.9515 | -0.7030 | 0.040 |
| C4_x0.1 | 34464 | -0.9299 | -0.7036 | 0.045 |

- AC4.2, C2 beats B1 by more than 3 x MDE: passes.
- AC4.3, the C1 interval against B1 includes 0: fails.
- C3, mean BEF of B3 by latency, bp: zero -0.9365, high -0.9385; flag (a non-zero latency above zero latency): False.
- C4, matches B3 within the interval: {'C4_x0.1': False, 'C4_x10': False}.

Statement from eval/analysis.canaries: The signal's gain does not depend on event signs, so it is not order-flow information. Primary result reported but not interpreted. C2, the oracle, beat B1 by 2.10 bp, more than 3 times the MDE. C3, zero latency, was above B3 at every non-zero latency on the mean. C4_x0.1 differed from B3; C4_x10 differed from B3.

## Random-pull controls (section 10, C1 rule revised 2026-10-26; exploratory comparisons)

Run c274b2def28e (configs/runs/v2_random_pulls_val.yaml, commit e00de09), primary cell, 6 validation days. R is B1 that marks a side toxic at each 100 ms step with
probability r and pulls it, the side chosen at random; r on each day is the realised toxic
share of C1 (R1), B3 (R_B3) or B2b (R_B2b) in run 5d27bc8ae820. Three seeds each; the bare
label (R1) is the mean over the seeds of each day's value. B1, C1, B3 and B2b run again in
this run so each comparison is within one run; against run 5d27bc8ae820: identical fills on every day, largest BEF difference 0.0e+00 bp.

| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Toxic share | Toxic episodes an hour |
|---|---|---|---|---|---|
| B1 | 39004 | -0.9429 | -0.7063 | 0.0000 | 0 |
| C1 | 38095 | -0.9519 | -0.7133 | 0.0129 | 438 |
| R1 | 38263 | -0.9527 | -0.7143 | 0.0128 | 459 |
| R1_s1 | 38269 | -0.9539 | -0.7146 | 0.0129 | 460 |
| R1_s2 | 38244 | -0.9530 | -0.7143 | 0.0128 | 458 |
| R1_s3 | 38276 | -0.9514 | -0.7141 | 0.0128 | 457 |
| B3 | 31958 | -0.9385 | -0.7015 | 0.0413 | 1094 |
| R_B3 | 37059 | -0.9663 | -0.7252 | 0.0412 | 1452 |
| R_B3_s1 | 37083 | -0.9674 | -0.7251 | 0.0413 | 1455 |
| R_B3_s2 | 37020 | -0.9668 | -0.7254 | 0.0412 | 1449 |
| R_B3_s3 | 37074 | -0.9646 | -0.7251 | 0.0412 | 1450 |
| B2b | 32597 | -0.9330 | -0.7129 | 0.2562 | 338 |
| R_B2b | 32518 | -0.9952 | -0.7527 | 0.2561 | 8017 |
| R_B2b_s1 | 32548 | -0.9929 | -0.7529 | 0.2562 | 8024 |
| R_B2b_s2 | 32495 | -0.9922 | -0.7531 | 0.2561 | 8015 |
| R_B2b_s3 | 32510 | -1.0006 | -0.7520 | 0.2559 | 8011 |

### C1 against R1 (the section 10 pass rule since 2026-10-26)

| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |
|---|---|---|---|---|---|---|
| C1 - R1 (pass: interval includes 0) | 6 | 0.0009 | [-0.0023, 0.0038] | [-0.0036, 0.0053] | 3 | none |
| C1 - B1 (the rule first written, reported) | 6 | -0.0090 | [-0.0126, -0.0055] | [-0.0142, -0.0038] | 0 | none |
| C1 - B3 (descriptive) | 6 | -0.0134 | [-0.0214, -0.0070] | [-0.0237, -0.0031] | 0 | none |
| C1 - R1_s1 (one seed) | 6 | 0.0020 | [-0.0009, 0.0052] | [-0.0025, 0.0066] | 3 | none |
| C1 - R1_s2 (one seed) | 6 | 0.0011 | [-0.0013, 0.0036] | [-0.0026, 0.0048] | 3 | none |
| C1 - R1_s3 (one seed) | 6 | -0.0005 | [-0.0047, 0.0033] | [-0.0064, 0.0054] | 4 | none |
| R1 - B1 (the cost of random pulls at C1's rate) | 6 | -0.0099 | [-0.0119, -0.0079] | [-0.0129, -0.0069] | 0 | none |

- AC4.3 as revised, the C1 interval against R1 includes 0: passes.
- Statement from eval/analysis.canaries on this run: C1, shuffled signs, did not differ detectably from R1.

### Exploratory: the selected overlays against random pulls at their own rates

Exploratory, not a test of section 7 or 10. Reported in the paper as exploratory.

| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |
|---|---|---|---|---|---|---|
| B3 - R_B3 | 6 | 0.0278 | [0.0227, 0.0351] | [0.0186, 0.0370] | 6 | none |
| B2b - R_B2b | 6 | 0.0622 | [0.0298, 0.1007] | [0.0115, 0.1128] | 6 | none |
| R_B3 - B1 | 6 | -0.0234 | [-0.0286, -0.0189] | [-0.0305, -0.0163] | 0 | none |
| R_B2b - B1 | 6 | -0.0524 | [-0.0730, -0.0346] | [-0.0795, -0.0252] | 0 | none |

Limitation, read with these rows: R pulls independently at each step, so it starts a new
pulled run more often than a signal whose marks persist (toxic episodes an hour in the
table above), and each new run gives up the queue place once. R_B3 starts 1.3
times as many runs as B3 and R_B2b 23.7 times as many as B2b, so B3 - R_B3 and
B2b - R_B2b mix what the signal chooses with how often it pulls, and overstate the signal's
part most where the ratio is largest; their order may not hold under a control matched on
run length as well. C1 starts 0.96 times as many runs as R1, so C1 - R1 is close to
matched.

### Exploratory: B3 against B2b at matched p

Runs 0bd4181a312a, 9e93e4415b6b. Exploratory; the selected B3 is p 0.05
and the selected B2b p 0.25, so H1's pair compares different pull rates.

Tuning runs, primary cell; K pull, magnitude rule off, B2b at tau 5 s.

| p | B3 - B2b mean bp | Bootstrap 95% | t 95% | Days > 0 | B3 BEF bp | B2b BEF bp | B3 toxic share | B2b toxic share | B3 cancels an hour | B2b cancels an hour | B3 / B2b notional |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.05 | -0.0010 | [-0.0067, 0.0049] | [-0.0093, 0.0073] | 2 | -0.9385 | -0.9375 | 0.041 | 0.042 | 2529 | 2090 | 0.837 |
| 0.1 | -0.0273 | [-0.0382, -0.0153] | [-0.0438, -0.0108] | 0 | -0.9604 | -0.9331 | 0.087 | 0.095 | 3499 | 2119 | 0.786 |
| 0.25 | -0.0627 | [-0.0947, -0.0322] | [-0.1072, -0.0183] | 0 | -0.9958 | -0.9330 | 0.228 | 0.256 | 6494 | 2142 | 0.726 |
| 0.5 | -0.0781 | [-0.1398, -0.0217] | [-0.1625, 0.0064] | 1 | -1.0304 | -0.9523 | 0.464 | 0.517 | 8809 | 1992 | 0.722 |

Limitation, read with this table: at the same p the two signals mark in runs of different
length. B3 cancels 1.2 to 4.4 times as often as B2b across these p (cancels
columns), so part of B3's deficit at matched p may be the cost of re-queuing rather than
worse information. B3 trades 0.72 to 0.84 of B2b's notional (last column, all
six days pooled).
