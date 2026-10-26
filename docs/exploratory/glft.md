# GLFT as a quoting model (exploratory)

GLFT was B1 in the v1 design. v2 replaced it with a join-the-touch base (PREREGISTRATION.md,
Design history), so GLFT is no longer a strategy of the study and this file reports it as
an exploratory result. Everything comes from committed runs on training and validation days
through scripts/glft_report.py; no new run was made for it. The GLFT code is unchanged in
src/toxic_flow/strategies/b1_glft.py and strategies/overlay.py, following the hftbacktest
GLFT tutorial with outward rounding.

## What the runs show

- Risk aversion trades fills for less adverse selection per fill. Over the training-day
  grid, raising gamma from 0.025 to 0.4 moves the quotes away from the mid, cuts the
  median day from about 8,000 fills to about 120, and raises the mean daily break-even fee
  (BEF) from about -0.86 to about -0.55 to -0.66 bp. The 1 s markout improves only from
  -0.73 to -0.58 bp. Each fill is still adversely selected; GLFT just takes fewer of them.
- No setting with enough fills breaks even before fees. The only positive mean, gamma 0.8
  with an 80-minute window, rests on a median of 28 fills a day; the other four gamma 0.8
  windows have a day with no fills at all. The section 4 floor of 100 median fills (v1)
  excluded them.
- The chosen setting (gamma 0.4, 10 minutes) gives the same picture in all 8 queue and
  latency cells: about 140 fills a day and a mean BEF of -0.54 to -0.59 bp, with no day
  without fills. The queue model barely matters because the quotes are far from the touch,
  where queue position is rarely the question.
- GLFT works in ticks, so its distance from the mid grows with the price. At gamma 0.4 the
  bid sat about 150 ticks (3.4 bp) from mid at 44,000 USDT on 2024-01-01 and about 730 ticks
  (7.5 bp) at 97,000 on 2024-12-01; on the validation days, at 85,000 to 106,000, it sat 750
  to 990 ticks (7.4 to 10.3 bp) away and traded 6 to 28 times a day. Across the 18 days the
  correlation of the mid with the distance in ticks is 0.92. A likely mechanism, not
  measured here (no run logged A, k or sigma): the arrival fit measures market-order depth
  in ticks, the same move in percent is more ticks at a higher price, so the fitted k falls
  and the half-spread widens.
- Beside the touch base on the same training days, GLFT loses less per unit of notional
  (-0.57 against -0.93 bp) on about 400 times fewer fills. The touch base trades about
  59,000 times a day and its fills mark out at -0.72 bp after 1 s.
- As the base for the v1 overlays it failed. On the validation days GLFT averaged +0.66 bp
  on 6 to 28 fills a day, carried by a few sweeps, and the v1 oracle C2 lost 0.87 bp a day
  against it (docs/M4_diagnosis.md gives why). That failure is what led to v2.

Limitations: the mean of daily BEF weights a day with 8 fills like a day with 300, so the
GLFT means on the validation days are noisy; the selection of gamma used the training-day
grid only; and every number here is in the simulation with the queue and latency models of
section 3, so none of it says what GLFT would do on the venue.

## Grid on the training days

Run ccbf1a18e770 (configs/runs/train_select_window.yaml, commit a0e0241), 12 training days, primary cell, full day. Each gamma has five windows (5, 10, 20, 40 and
80 minutes); the BEF columns give the lowest and highest of their mean daily BEF, over the
windows where it is defined (a window with a day without fills has none).

| gamma | Windows with a mean BEF | Mean daily BEF bp, lowest | highest | Median daily fills | Markout 1 s bp | Markout 60 s bp |
|---|---|---|---|---|---|---|
| 0.025 | 5 of 5 | -0.866 | -0.852 | 8034 | -0.728 | -0.864 |
| 0.05 | 5 of 5 | -0.819 | -0.812 | 5127 | -0.694 | -0.821 |
| 0.1 | 5 of 5 | -0.798 | -0.772 | 2280 | -0.679 | -0.784 |
| 0.2 | 5 of 5 | -0.705 | -0.681 | 608 | -0.623 | -0.695 |
| 0.4 | 5 of 5 | -0.663 | -0.551 | 122 | -0.580 | -0.618 |
| 0.8 | 1 of 5 | 0.410 | 0.410 | 28 | -0.128 | -0.025 |

## The chosen setting in all 8 cells

Run 633a29217f4b (configs/runs/train_chosen_window.yaml, commit 2e174b6), gamma 0.4 and a 10-minute window, 12 training days. Means over days.

| Queue model | Latency | Fills a day | Mean daily BEF bp | Markout 1 s bp | Markout 60 s bp | Days without fills |
|---|---|---|---|---|---|---|
| risk_averse | low | 138.2 | -0.594 | -0.552 | -0.633 | 0 |
| risk_averse | high | 145.5 | -0.565 | -0.559 | -0.591 | 0 |
| power3 | low | 138.5 | -0.587 | -0.544 | -0.623 | 0 |
| power3 | high | 145.7 | -0.560 | -0.550 | -0.581 | 0 |
| power2 | low | 138.5 | -0.586 | -0.544 | -0.621 | 0 |
| power2 | high | 145.7 | -0.559 | -0.549 | -0.580 | 0 |
| log | low | 138.8 | -0.570 | -0.534 | -0.600 | 0 |
| log | high | 146.0 | -0.539 | -0.540 | -0.554 | 0 |

## Distance from the mid and the price level

| Day | Split | Mid at the mark | gamma 0.4: bid from mid, ticks | in bp | fills | gamma 0.2: ticks | fills |
|---|---|---|---|---|---|---|---|
| 2024-01-01 | train | 44210 | 149.5 | 3.38 | 252 | 89.5 | 1046 |
| 2024-02-01 | train | 43070 | 175.5 | 4.07 | 300 | 107.5 | 1520 |
| 2024-03-01 | train | 62428 | 362.5 | 5.81 | 132 | 202.5 | 988 |
| 2024-04-01 | train | 69711 | 410.5 | 5.89 | 88 | 225.5 | 566 |
| 2024-05-01 | train | 58288 | 494.5 | 8.48 | 210 | 267.5 | 1192 |
| 2024-06-01 | train | 67807 | 225.5 | 3.33 | 124 | 135.5 | 312 |
| 2024-07-01 | train | 62909 | 371.5 | 5.91 | 88 | 209.5 | 352 |
| 2024-08-01 | train | 65381 | 469.5 | 7.18 | 104 | 257.5 | 482 |
| 2024-09-01 | train | 57306 | 326.5 | 5.70 | 134 | 185.5 | 612 |
| 2024-10-01 | train | 60816 | 301.5 | 4.96 | 180 | 171.5 | 782 |
| 2024-11-01 | train | 69513 | 430.5 | 6.19 | 102 | 238.5 | 358 |
| 2024-12-01 | train | 97250 | 726.5 | 7.47 | 32 | 397.5 | 208 |
| 2025-01-01 | val | 94585 | 842.5 | 8.91 | 8 | 451.5 | 44 |
| 2025-02-01 | val | 100642 | 747.5 | 7.43 | 28 | 399.5 | 124 |
| 2025-03-01 | val | 86030 | 760.5 | 8.84 | 20 | 411.5 | 104 |
| 2025-04-01 | val | 85126 | 858.5 | 10.09 | 8 | 454.5 | 62 |
| 2025-05-01 | val | 96438 | 989.5 | 10.26 | 14 | 527.5 | 54 |
| 2025-06-01 | val | 105546 | 964.5 | 9.14 | 6 | 504.5 | 50 |

Correlation across the 18 days between the mid and the gamma 0.4 distance in ticks: 0.923.

## GLFT beside the touch base

Run a582f2864e78 (configs/runs/diag_train_touch.yaml, commit 9315a55), 12 training days, primary cell. T0 is the join-the-touch base, which v2 adopted as B1.

| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Markout 60 s bp |
|---|---|---|---|---|
| GLFT, gamma 0.4 | 146 | -0.565 | -0.559 | -0.591 |
| GLFT, gamma 0.2 | 702 | -0.687 | -0.626 | -0.693 |
| Touch, skew 1 tick | 58978 | -0.933 | -0.717 | -0.943 |

## v1 overlays and the oracle on GLFT

Runs b63a70c9a965 (tune_val) and 9eaa1b3d693c (canaries_val_draft), 6 validation days, primary cell.

| Overlay on GLFT | Best mean daily BEF bp | Its c, d | Worst mean daily BEF bp |
|---|---|---|---|
| B2 | 0.862 | 0, 1 | -0.806 |
| B2b | 0.660 | 0, 0 | -0.923 |
| B3 | 0.660 | 0, 0 | -0.000 |

B1 (GLFT) mean daily BEF on these days: 0.660 bp. C2 - B1: -0.872 bp, bootstrap [-1.783, -0.066], 2 of 6 days above 0.

