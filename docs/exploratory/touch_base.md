# A base that trades: join the touch (exploratory, items 9 to 12)

Exploratory throughout. T0 quotes at the best bid and ask, skews both quotes one tick per
order size of inventory, and keeps the same order size, inventory cap and engine as B1. The
overlays B2b and B3 and the oracle C2 are then laid on it (centre = r + c u delta with delta
half the spread, width delta (1 + d m)). Ranking the overlays on training days, as here, is
not the pre-registered procedure (section 4 tunes overlays on validation days); nothing
here selects anything. Tables from scripts/touch_base.py.

Run a582f2864e78 (configs/runs/diag_train_touch.yaml, commit 9315a55),
12 training days. Exploratory throughout.

## 9. The touch base T0 in all 8 cells

Mean over days. Markouts per fill in our favour, averaged per day.

| Queue model | Latency | Fills a day | BEF bp | Markout 1 s bp | Markout 10 s bp | Markout 60 s bp | Both sides resting | Bid at best |
|---|---|---|---|---|---|---|---|---|
| risk_averse | low | 66150 | -0.936 | -0.724 | -0.905 | -0.947 | 0.759 | 0.524 |
| risk_averse | high | 58978 | -0.933 | -0.717 | -0.901 | -0.943 | 0.775 | 0.524 |
| power3 | low | 68939 | -0.917 | -0.705 | -0.885 | -0.926 | 0.773 | 0.527 |
| power3 | high | 61679 | -0.912 | -0.696 | -0.881 | -0.922 | 0.788 | 0.528 |
| power2 | low | 69001 | -0.916 | -0.703 | -0.884 | -0.925 | 0.773 | 0.527 |
| power2 | high | 61737 | -0.911 | -0.694 | -0.879 | -0.920 | 0.789 | 0.528 |
| log | low | 71733 | -0.891 | -0.682 | -0.860 | -0.898 | 0.784 | 0.531 |
| log | high | 64386 | -0.886 | -0.671 | -0.854 | -0.893 | 0.799 | 0.532 |

Against B1 (selected) and B1 at gamma 0.2 in the primary cell:

| Strategy | Fills a day | BEF bp |
|---|---|---|
| T0 | 58978 | -0.933 |
| B1 | 146 | -0.565 |
| B1_g0.2 | 702 | -0.687 |
| C2_touch | 58530 | -0.914 |

## 10. Overlays and C2 on the touch base (primary cell, exploratory tuning on training days)

### B3_touch

| Candidate | Mean daily BEF bp | Pooled BEF bp | Median fills | Days without fills |
|---|---|---|---|---|
| {"c": 0.0, "d": 0.0} | -0.933 | -0.942 | 59858 | 0 |
| {"c": 1.0, "d": 0.0} | -0.940 | -0.949 | 59339 | 0 |
| {"c": 0.5, "d": 0.0} | -0.941 | -0.950 | 59294 | 0 |
| {"c": 1.0, "d": 0.5} | -0.942 | -0.952 | 59129 | 0 |
| {"c": 0.0, "d": 0.5} | -0.942 | -0.951 | 59407 | 0 |
| {"c": 0.5, "d": 0.5} | -0.942 | -0.951 | 59089 | 0 |
| {"c": 0.0, "d": 1.0} | -0.944 | -0.952 | 59298 | 0 |
| {"c": 1.0, "d": 1.0} | -0.944 | -0.953 | 58982 | 0 |
| {"c": 0.5, "d": 1.0} | -0.944 | -0.953 | 58926 | 0 |

### B2b_touch

| Candidate | Mean daily BEF bp | Pooled BEF bp | Median fills | Days without fills |
|---|---|---|---|---|
| {"c": 0.0, "d": 0.0, "tau_s": 1.0} | -0.933 | -0.942 | 59858 | 0 |
| {"c": 0.0, "d": 0.0, "tau_s": 30.0} | -0.933 | -0.942 | 59858 | 0 |
| {"c": 0.0, "d": 0.0, "tau_s": 5.0} | -0.933 | -0.942 | 59858 | 0 |
| {"c": 0.5, "d": 0.0, "tau_s": 30.0} | -0.937 | -0.946 | 59177 | 0 |
| {"c": 1.0, "d": 0.0, "tau_s": 5.0} | -0.937 | -0.946 | 59154 | 0 |
| {"c": 1.0, "d": 0.0, "tau_s": 30.0} | -0.938 | -0.946 | 59180 | 0 |
| {"c": 0.0, "d": 0.5, "tau_s": 30.0} | -0.938 | -0.946 | 59171 | 0 |
| {"c": 0.5, "d": 0.0, "tau_s": 5.0} | -0.938 | -0.947 | 59122 | 0 |
| {"c": 0.0, "d": 0.5, "tau_s": 5.0} | -0.938 | -0.947 | 59202 | 0 |
| {"c": 1.0, "d": 0.0, "tau_s": 1.0} | -0.938 | -0.947 | 59101 | 0 |
| {"c": 1.0, "d": 0.5, "tau_s": 5.0} | -0.938 | -0.947 | 58939 | 0 |
| {"c": 0.0, "d": 1.0, "tau_s": 30.0} | -0.939 | -0.947 | 59095 | 0 |
| {"c": 0.5, "d": 0.0, "tau_s": 1.0} | -0.939 | -0.947 | 59074 | 0 |
| {"c": 0.0, "d": 0.5, "tau_s": 1.0} | -0.939 | -0.947 | 59206 | 0 |
| {"c": 1.0, "d": 0.5, "tau_s": 30.0} | -0.939 | -0.948 | 58973 | 0 |
| {"c": 0.0, "d": 1.0, "tau_s": 5.0} | -0.939 | -0.948 | 59103 | 0 |
| {"c": 0.5, "d": 0.5, "tau_s": 5.0} | -0.939 | -0.948 | 58874 | 0 |
| {"c": 1.0, "d": 0.5, "tau_s": 1.0} | -0.939 | -0.949 | 58925 | 0 |
| {"c": 0.5, "d": 0.5, "tau_s": 30.0} | -0.939 | -0.948 | 58915 | 0 |
| {"c": 1.0, "d": 1.0, "tau_s": 5.0} | -0.940 | -0.948 | 58807 | 0 |
| {"c": 1.0, "d": 1.0, "tau_s": 30.0} | -0.940 | -0.949 | 58830 | 0 |
| {"c": 0.0, "d": 1.0, "tau_s": 1.0} | -0.940 | -0.949 | 59100 | 0 |
| {"c": 0.5, "d": 0.5, "tau_s": 1.0} | -0.940 | -0.949 | 58852 | 0 |
| {"c": 0.5, "d": 1.0, "tau_s": 30.0} | -0.941 | -0.949 | 58765 | 0 |
| {"c": 0.5, "d": 1.0, "tau_s": 5.0} | -0.941 | -0.949 | 58719 | 0 |
| {"c": 1.0, "d": 1.0, "tau_s": 1.0} | -0.941 | -0.950 | 58767 | 0 |
| {"c": 0.5, "d": 1.0, "tau_s": 1.0} | -0.942 | -0.950 | 58715 | 0 |

The B2 (OFI) grid on this base (configs/runs/diag_train_touch_b2.yaml) was not run for
time; B2 enters neither H1 nor the power projection.

| Comparison | Days | Mean daily BEF difference bp | Bootstrap 95% | t 95% | Days > 0 |
|---|---|---|---|---|---|
| C2_touch - T0 | 12 | 0.018 | [0.014, 0.022] | [0.014, 0.023] | 12 |
| T0 - B1 | 12 | -0.367 | [-0.781, 0.007] | [-0.826, 0.091] | 4 |

## 11. Power projection on this base (training days)

s is the standard deviation of the daily D_i = BEF_B3 - BEF_B2b; MDE = 2.80 s / sqrt(16);
days needed for an MDE of 0.1 bp = (2.80 s / 0.1)^2. Pairs: the best mean
BEF of each (as section 4 would pick, but on training days), and the best with c or d above 0.

| B3 setting | B2b setting | Days | Mean D bp | s bp | MDE on 16 days bp | Days for MDE 0.1 bp |
|---|---|---|---|---|---|---|
| {"c": 0.0, "d": 0.0} | {"c": 0.0, "d": 0.0, "tau_s": 5.0} | 12 | 0.000 | 0.000 | 0.000 | 0 |
| {"c": 1.0, "d": 0.0} | {"c": 0.5, "d": 0.0, "tau_s": 30.0} | 12 | -0.003 | 0.004 | 0.003 | 1 |

Reading item 11: on this base the daily difference between B3 and B2b is very stable
(s about 0.004 bp), so 16 days could detect a difference of about 0.003 bp, and one day
would already give an MDE below 0.1 bp. The catch is the size of the effects: the best
overlays move the break-even fee by 0.01 bp or less, and none beats the base itself.
When both picks are c = d = 0 the two strategies are identical and s is 0, as on the GLFT
base (Q47).

## 12. What a redesign would gain and cost

Gain: a base at the touch trades every day in every cell (about 59,000 fills a day), so
the day-level comparisons are precise, and the oracle beats its base on every training
day (+0.018 bp, item 10), which is what AC4.2 is meant to show; the C2 failure in M4 came
from the far-quoting GLFT base, not from the harness. Cost: the touch base loses about
0.93 bp of notional before fees in all 8 cells, so every strategy in such a design is
deep under the 2 bp maker fee, and the overlays tested here change its break-even fee by
hundredths of a basis point while the signals predict the next ticks with correlations of
0.1 to 0.2 (docs/exploratory/signal_information.md). A redesign would turn the question
into "does Hawkes reduce adverse selection at the touch by a measurable amount", with high
power for very small effects, and it would replace the pre-registered GLFT base, the B0/B1
selection and the K constants' role, all after results were seen: every such change goes
into DEVIATIONS.md or a fresh pre-registration, which is for Ilia and chat to decide.
