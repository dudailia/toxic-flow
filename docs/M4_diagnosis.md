# M4 diagnosis: why C2 fails (exploratory)

C2, the oracle canary, failed AC4.2 on the validation days (docs/M4_draft.md). Per Ilia
(2026-10-24) this file diagnoses before any design change. Everything here is
exploratory, on training and validation days only, primary cell (risk-averse queue model,
high latency) unless a cell is named. Nothing in PREREGISTRATION.md or
configs/selected.yaml changed. Tables come from scripts/m4_diagnosis.py over the two
committed diagnosis runs; the text and the ranked section at the end are mine.

Item 1 conclusion: there is no sign bug. Unit tests (tests/canary/test_c2_oracle.py) show
that the oracle's u equals the sign of the mid change 5 s ahead on a random book, and that
inside the loop every C2 quote equals the section 4 overlay of its own step, centre =
r + u * half, so u = +1 lifts both quotes. On the validation days, C2 with u flipped loses
0.95 bp a day more than C2 (bootstrap [-0.97, -0.93], 0 of 6 days above), so the harness
does turn the oracle's direction into PnL; it is not enough to beat B1. No fix and no
canary rerun were needed.

Item 2 conclusion: C2 still loses to B1 in the easiest cell, the log queue model at zero
latency (-0.99 bp a day, bootstrap [-1.85, -0.25]). Latency and queue pessimism are not
the reason.

Item 4 conclusion: yes, the grid extension pushed B1 too wide, and the price level did
the rest. GLFT works in ticks, and its distance from mid grows with the BTC price: from
150 ticks (3.4 bp) at 44k on 2024-01-01 to 730 ticks (7.5 bp) at 97k on 2024-12-01, and
about 860 ticks (9 bp) on the validation days at 85k to 106k. Going from gamma 0.2 to 0.4
widened the training-day distance from 207 to 370 ticks and cut fills from 702 to 146 a
day; on validation days, from 458 to 860 ticks and from 73 to 14 fills.

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

## 4. Why B1 barely trades

| Strategy | Days | Fills a day | BEF bp | Bid from mid, ticks | Ask from mid, ticks | Bid at best | Both sides resting |
|---|---|---|---|---|---|---|---|
| B1 train | 12 | 145.500 | -0.565 | 370.333 | 370.250 | 0.001 | 1.000 |
| B1 val | 6 | 14.000 | 0.660 | 860.500 | 860.500 | 0.000 | 1.000 |
| B1_g0.2 train | 12 | 701.500 | -0.687 | 207.333 | 207.500 | 0.007 | 0.999 |
| B1_g0.2 val | 6 | 73.000 | -0.354 | 458.167 | 458.167 | 0.000 | 1.000 |

Fills a day and the mid (USDT) by day, B1 at the selected setting:

| Day | Split | B1 fills | B1_g0.2 fills | Mid at the mark | B1 bid from mid, ticks |
|---|---|---|---|---|---|
| 2024-01-01 | train | 252 | 1046 | 44210 | 149.5 |
| 2024-02-01 | train | 300 | 1520 | 43070 | 175.5 |
| 2024-03-01 | train | 132 | 988 | 62428 | 362.5 |
| 2024-04-01 | train | 88 | 566 | 69711 | 410.5 |
| 2024-05-01 | train | 210 | 1192 | 58288 | 494.5 |
| 2024-06-01 | train | 124 | 312 | 67807 | 225.5 |
| 2024-07-01 | train | 88 | 352 | 62909 | 371.5 |
| 2024-08-01 | train | 104 | 482 | 65381 | 469.5 |
| 2024-09-01 | train | 134 | 612 | 57306 | 326.5 |
| 2024-10-01 | train | 180 | 782 | 60816 | 301.5 |
| 2024-11-01 | train | 102 | 358 | 69513 | 430.5 |
| 2024-12-01 | train | 32 | 208 | 97250 | 726.5 |
| 2025-01-01 | val | 8 | 44 | 94585 | 842.5 |
| 2025-02-01 | val | 28 | 124 | 100642 | 747.5 |
| 2025-03-01 | val | 20 | 104 | 86030 | 760.5 |
| 2025-04-01 | val | 8 | 62 | 85126 | 858.5 |
| 2025-05-01 | val | 14 | 54 | 96438 | 989.5 |
| 2025-06-01 | val | 6 | 50 | 105546 | 964.5 |

B1 (selected) by UTC hour, median over days of the hourly median distance:

| Hour | Train bid ticks | Train ask ticks | Train fills | Val bid ticks | Val ask ticks | Val fills |
|---|---|---|---|---|---|---|
| 0 | 327.5 | 327.5 | 2.2 | 853.0 | 853.0 | 0.3 |
| 1 | 387.5 | 387.2 | 6.6 | 934.8 | 934.8 | 0.3 |
| 2 | 345.0 | 345.0 | 6.7 | 854.2 | 854.0 | 0.3 |
| 3 | 292.5 | 292.5 | 3.7 | 830.0 | 830.0 | 0.0 |
| 4 | 304.0 | 304.0 | 4.7 | 792.8 | 792.8 | 1.3 |
| 5 | 302.5 | 302.4 | 7.2 | 713.5 | 713.5 | 0.0 |
| 6 | 321.2 | 320.8 | 4.2 | 772.5 | 772.5 | 1.0 |
| 7 | 317.0 | 317.5 | 6.5 | 749.2 | 749.2 | 0.0 |
| 8 | 300.5 | 300.0 | 3.3 | 683.0 | 683.0 | 0.7 |
| 9 | 291.0 | 290.8 | 1.3 | 769.5 | 769.5 | 0.7 |
| 10 | 313.0 | 313.0 | 3.8 | 758.0 | 758.0 | 1.3 |
| 11 | 313.5 | 311.5 | 5.0 | 782.5 | 782.5 | 0.0 |
| 12 | 294.5 | 295.0 | 6.3 | 749.5 | 749.5 | 0.3 |
| 13 | 370.0 | 370.0 | 6.7 | 781.0 | 781.0 | 0.0 |
| 14 | 496.0 | 496.0 | 10.8 | 982.0 | 982.0 | 0.3 |
| 15 | 459.5 | 459.5 | 10.3 | 857.1 | 857.1 | 0.7 |
| 16 | 499.0 | 499.5 | 7.0 | 872.0 | 872.0 | 0.7 |
| 17 | 445.0 | 445.0 | 10.3 | 920.5 | 920.0 | 0.7 |
| 18 | 402.0 | 402.0 | 5.6 | 861.0 | 861.0 | 1.7 |
| 19 | 417.8 | 417.5 | 6.6 | 849.0 | 849.0 | 1.7 |
| 20 | 530.0 | 530.0 | 8.5 | 875.0 | 875.0 | 0.0 |
| 21 | 434.5 | 434.5 | 7.0 | 1057.0 | 1057.0 | 0.7 |
| 22 | 391.5 | 391.5 | 4.7 | 1011.2 | 1010.5 | 0.3 |
| 23 | 366.5 | 366.5 | 6.5 | 983.0 | 983.0 | 1.0 |

## 5. Exploratory base on training days: join the touch (T0)

T0 quotes at the best bid and ask with one tick of inventory skew per order size
and the same cap; C2_touch is the oracle overlay (c = 1, m = 0) on it. Primary cell.

| Strategy | Days | Fills a day | BEF bp | Markout 1 s bp | Markout 10 s bp | Markout 60 s bp | Cancels an hour | Median order-to-fill s | Bid at best | Ask at best | Both sides resting | Bid from mid, ticks | Ask from mid, ticks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 12 | 145.500 | -0.565 | -0.559 | -0.570 | -0.591 | 7111.306 | 0.166 | 0.001 | 0.001 | 1.000 | 370.333 | 370.250 |
| T0 | 12 | 58977.833 | -0.933 | -0.717 | -0.901 | -0.943 | 3529.475 | 0.436 | 0.524 | 0.527 | 0.775 | 0.500 | 0.500 |
| C2_touch | 12 | 58530.000 | -0.914 | -0.716 | -0.882 | -0.923 | 3816.593 | 0.421 | 0.507 | 0.510 | 0.785 | 0.500 | 0.500 |

| Comparison | Cell | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |
|---|---|---|---|---|---|---|
| C2_touch - T0 | risk_averse / high | 12 | 0.018 | [0.014, 0.022] | [0.014, 0.023] | 12 |
| T0 - B1 | risk_averse / high | 12 | -0.367 | [-0.781, 0.007] | [-0.826, 0.091] | 4 |


Item 5 conclusion: quoting at the touch, the base trades about 59,000 times a day and its
break-even fee is -0.93 bp, with adverse markouts of -0.72 bp at 1 s and -0.94 bp at
60 s. The oracle on that base beats it on every training day, by 0.018 bp a day
(bootstrap [0.014, 0.022]). So the harness converts the oracle's information into PnL on
a base that trades at the touch, but the gain is two orders of magnitude below the
adverse selection that the base pays.

## What I think is wrong (ranked by evidence)

1. Passive quoting in this market loses about 0.9 bp of notional to adverse selection,
   and the spread pays almost nothing. BTCUSDT's spread is one tick, about 0.01 bp at
   these prices, while fills at the touch mark out at -0.7 to -0.9 bp in every queue
   model and latency (touch base, items 5 and 9). Every strategy here has a negative
   break-even fee on the training days. Before any fee, there is no edge for an overlay
   to improve on, and the 2 bp standard maker fee is far away. Strong evidence: 12
   training days, all 8 cells, about 59,000 fills a day.
2. B1 at the selected setting is a poor base: it quotes far from the market, so it
   barely trades. 370 ticks from mid on training days and 860 on validation days, never
   at the best price; 146 and 14 fills a day. The grid extension (Q41) doubled the
   distance, and GLFT in tick units widens further as the price rises. Its validation
   mean of +0.66 bp rests on a few sweeps. Strong evidence: measured on every day.
3. AC4.2 compares C2 with B1, but on this base C2 is not "B1 plus information". With
   c = 1 the centre moves by a whole GLFT half-spread, which puts one side at the touch
   about a quarter of the time, so C2 trades about 9,400 times a day at the touch
   instead of B1's 14 far fills and inherits the adverse selection of cause 1. On the
   touch base, where both sides trade alike, the same oracle beats its base on 12 of 12
   days. Strong evidence.
4. Constant re-quoting: B1 and C2 send about 4,700 cancels an hour on validation days and
   7,100 (B1) on training days, one at almost every step the mid moves. A replaced order
   goes to the back of the queue. Weak to moderate evidence: the touch base cancels half
   as often and still loses as much, so this is not the main cause.
5. Not latency or queue pessimism (item 2), and not a sign bug (item 1). Strong evidence
   against both.
