# M4 diagnosis: why C2 fails (exploratory)

C2, the oracle canary, failed AC4.2 on the validation days (docs/M4_draft.md). Per Ilia
(2026-10-24) this file diagnoses before any design change. Everything here is
exploratory, on training and validation days only, primary cell (risk-averse queue model,
high latency) unless a cell is named. Nothing in PREREGISTRATION.md or
configs/selected.yaml changed. Tables come from scripts/m4_diagnosis.py over committed
runs; the text and the ranked section at the end are mine.

Status: items 1 to 3 are complete. Item 4 is partial and item 5 is not done, because the
instrumented training run (configs/runs/diag_train_touch.yaml) stopped at the disk floor
twice; see docs/SESSION_REPORT.md.

Item 1 conclusion: there is no sign bug. Unit tests (tests/canary/test_c2_oracle.py) show
that the oracle's u equals the sign of the mid change 5 s ahead on a random book, and that
inside the loop every C2 quote equals the section 4 overlay of its own step, centre =
r + u * half, so u = +1 lifts both quotes. On the validation days, C2 with u flipped loses
0.95 bp a day more than C2 (bootstrap [-0.97, -0.93], 0 of 6 days above), so the harness
does turn the oracle's direction into PnL; it is not enough to beat B1. No fix and no
canary rerun were needed.

Runs: validation 4de702fe5d20 (configs/runs/diag_val.yaml, commit 7ed144f). Exploratory throughout.

## 1. Sign check

| Comparison | Cell | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |
|---|---|---|---|---|---|---|
| C2 - B1 | risk_averse / high | 6 | -0.872 | [-1.783, -0.066] | [-2.120, 0.376] | 2 |
| C2_flip - B1 | risk_averse / high | 6 | -1.825 | [-2.732, -1.027] | [-3.058, -0.593] | 0 |
| C2_flip - C2 | risk_averse / high | 6 | -0.953 | [-0.971, -0.930] | [-0.983, -0.923] | 0 |

## 2. C2 against B1 in the easiest cell (log queue model, zero latency)

| Comparison | Cell | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |
|---|---|---|---|---|---|---|
| C2_easy - B1_easy | log / zero | 6 | -0.992 | [-1.848, -0.248] | [-2.148, 0.163] | 1 |

| Strategy | Days | Fills a day | BEF bp | Markout 1 s bp | Markout 10 s bp | Markout 60 s bp |
|---|---|---|---|---|---|---|
| B1_easy | 6 | 13.333 | 0.836 | 0.744 | 0.763 | 0.812 |
| C2_easy | 6 | 10933.333 | -0.157 | -0.552 | -0.169 | -0.154 |

## 3. Why C2 loses: B1 and C2 on the validation days (primary cell)

Mean over the 6 days. Markouts are per fill in our favour, averaged per day.
Order-to-fill is from the order's request to its fill at the exchange. At best:
share of decision steps with our target bid at or above the best bid (ask at or
below the best ask).

| Strategy | Days | Fills a day | BEF bp | Markout 1 s bp | Markout 10 s bp | Markout 60 s bp | Cancels an hour | Median order-to-fill s | Bid at best | Ask at best | Both sides resting | Bid from mid, ticks | Ask from mid, ticks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 6 | 14.000 | 0.660 | 0.518 | 0.524 | 0.674 | 4658.644 | 0.093 | 0.000 | 0.000 | 1.000 | 860.500 | 860.500 |
| C2 | 6 | 9379.333 | -0.212 | -0.605 | -0.223 | -0.211 | 4890.930 | 0.647 | 0.250 | 0.249 | 0.989 | 833.667 | 830.333 |
| C2_flip | 6 | 12179.500 | -1.165 | -0.784 | -1.141 | -1.159 | 4595.543 | 1.327 | 0.306 | 0.301 | 0.985 | 806.667 | 849.167 |

## 4. Why B1 barely trades (partial: the training diagnosis run did not finish)

Training-day fills from run ccbf1a18e770 (configs/runs/train_select_window.yaml),
the same B1 settings in the same cell; distance from mid is measured on validation days
only, because the instrumented training run stopped at the disk floor.

| Strategy | Training fills a day (mean) | Training BEF bp | Validation fills a day | Validation BEF bp | Validation bid from mid, ticks |
|---|---|---|---|---|---|
| B1 | 145.5 | -0.565 | 14.0 | 0.660 | 860.5 |
| B1_g0.2 | 701.5 | -0.687 | 73.0 | -0.354 | 458.2 |

Fills a day and the mid by day, B1 at the selected setting:

| Day | Split | B1 fills | B1_g0.2 fills | Mid at the mark |
|---|---|---|---|---|
| 2024-01-01 | train | 252 | 1046 | 44210 |
| 2024-02-01 | train | 300 | 1520 | 43070 |
| 2024-03-01 | train | 132 | 988 | 62428 |
| 2024-04-01 | train | 88 | 566 | 69711 |
| 2024-05-01 | train | 210 | 1192 | 58288 |
| 2024-06-01 | train | 124 | 312 | 67807 |
| 2024-07-01 | train | 88 | 352 | 62909 |
| 2024-08-01 | train | 104 | 482 | 65381 |
| 2024-09-01 | train | 134 | 612 | 57306 |
| 2024-10-01 | train | 180 | 782 | 60816 |
| 2024-11-01 | train | 102 | 358 | 69513 |
| 2024-12-01 | train | 32 | 208 | 97250 |
| 2025-01-01 | val | 8 | 44 | 94585 |
| 2025-02-01 | val | 28 | 124 | 100642 |
| 2025-03-01 | val | 20 | 104 | 86030 |
| 2025-04-01 | val | 8 | 62 | 85126 |
| 2025-05-01 | val | 14 | 54 | 96438 |
| 2025-06-01 | val | 6 | 50 | 105546 |

B1 (selected) on validation days by UTC hour, median over days:

| Hour | Bid from mid, ticks | Ask from mid, ticks | Fills (mean) |
|---|---|---|---|
| 0 | 853.0 | 853.0 | 0.33 |
| 1 | 934.8 | 934.8 | 0.33 |
| 2 | 854.2 | 854.0 | 0.33 |
| 3 | 830.0 | 830.0 | 0.00 |
| 4 | 792.8 | 792.8 | 1.33 |
| 5 | 713.5 | 713.5 | 0.00 |
| 6 | 772.5 | 772.5 | 1.00 |
| 7 | 749.2 | 749.2 | 0.00 |
| 8 | 683.0 | 683.0 | 0.67 |
| 9 | 769.5 | 769.5 | 0.67 |
| 10 | 758.0 | 758.0 | 1.33 |
| 11 | 782.5 | 782.5 | 0.00 |
| 12 | 749.5 | 749.5 | 0.33 |
| 13 | 781.0 | 781.0 | 0.00 |
| 14 | 982.0 | 982.0 | 0.33 |
| 15 | 857.1 | 857.1 | 0.67 |
| 16 | 872.0 | 872.0 | 0.67 |
| 17 | 920.5 | 920.0 | 0.67 |
| 18 | 861.0 | 861.0 | 1.67 |
| 19 | 849.0 | 849.0 | 1.67 |
| 20 | 875.0 | 875.0 | 0.00 |
| 21 | 1057.0 | 1057.0 | 0.67 |
| 22 | 1011.2 | 1010.5 | 0.33 |
| 23 | 983.0 | 983.0 | 1.00 |

## 5. Exploratory touch base on training days

Not done: the training run (configs/runs/diag_train_touch.yaml) stopped at the disk floor
after 173 of 564 cells and wrote no metrics. See docs/SESSION_REPORT.md.


## What I think is wrong (ranked by evidence)

1. B1 at the selected setting quotes far from the market, so it barely trades and is a
   poor base for any overlay. At gamma 0.4 and a 10 min window its median quote sits
   about 860 ticks (about 9 bp) from mid on validation days, never at the best price;
   it fills 14 times a day there and 146 on training days. The grid extension (Q41)
   doubled the distance from gamma 0.2 (458 ticks) and cut fills about five times. GLFT
   in tick units also widens as the price rises, and the validation days are at 85k to
   106k against 43k to 97k in training. Strong evidence: measured distances and fills on
   every day. Training-day distances are still missing (item 4 partial).
2. AC4.2 compares C2 with B1, but C2 is not "B1 plus information": with c = 1 the centre
   moves by a whole GLFT half-spread, which puts one side at the touch about a quarter
   of the time. C2 then trades about 9,400 times a day at the touch instead of B1's 14
   far fills. Its fills are adverse (1 s markout -0.6 bp per fill on average), while the
   oracle's edge, the sign of the next 5 s mid change, is small next to that. The flip
   test shows the information is used (0.95 bp a day, tight interval); the loss comes
   from switching the trading regime, not from a missing signal. Strong evidence on the
   validation days.
3. Constant re-quoting: B1 and C2 send about 4,700 cancels an hour, one at almost every
   step the mid moves, because the target follows the mid tick by tick. A replaced order
   goes to the back of the queue, so a quote at the touch fills mostly when its level is
   swept, the most adverse case. Moderate evidence: the cancel counts and the 0.65 s
   median order-to-fill time of C2 fit this, but no run isolates it yet.
4. Not latency or queue pessimism: in the log queue model at zero latency C2 still loses
   0.99 bp a day to B1 (bootstrap [-1.85, -0.25]). Strong evidence against this cause.
5. Not a sign bug: tests and the flip run (item 1). Strong evidence against this cause.
6. The validation days are thin for B1 (6 to 28 fills a day), so every day-level BEF of
   B1 rests on a few sweeps; this inflates B1's mean (0.66 bp, the best of any strategy
   in this study) and makes any comparison against it noisy. Moderate evidence.

Not yet tested, pending the training run: whether a base that quotes at the touch
(item 5) lets the oracle and the overlays show a gain.
