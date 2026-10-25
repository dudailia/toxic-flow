# M4 draft: overlay tuning, canaries and MDE (for Ilia's review)

Draft only. Nothing here is in PREREGISTRATION.md or configs/selected.yaml; every [TBD]
there is unchanged. All numbers come from the three runs named below, through
scripts/m4_draft.py. Validation and training days only; no test day was loaded.

## Overlay tuning on the validation days (section 4)

Run b63a70c9a965 (configs/runs/tune_val.yaml, commit 63fa2cc), primary cell risk_averse / high, 6 days: 2025-01-01, 2025-02-01, 2025-03-01, 2025-04-01, 2025-05-01, 2025-06-01. Rule: highest mean daily break-even fee; ties to the smaller c + d, then the shorter window or decay.

### B2

| Candidate | Mean daily BEF bp | Pooled BEF bp | Days without fills | Median daily fills |
|---|---|---|---|---|
| {"c": 0.0, "d": 1.0, "ofi_window_s": 1.0} | 0.8618 | 0.6006 | 0 | 10 |
| {"c": 0.0, "d": 0.5, "ofi_window_s": 1.0} | 0.7084 | 0.6248 | 0 | 10 |
| {"c": 0.0, "d": 0.0, "ofi_window_s": 5.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.0, "d": 0.0, "ofi_window_s": 1.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.0, "d": 0.0, "ofi_window_s": 30.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.5, "d": 1.0, "ofi_window_s": 1.0} | 0.3472 | 0.2329 | 0 | 10 |
| {"c": 0.5, "d": 0.5, "ofi_window_s": 1.0} | 0.2893 | 0.1433 | 0 | 11 |
| {"c": 0.0, "d": 0.5, "ofi_window_s": 30.0} | 0.2547 | 0.1988 | 0 | 10 |
| {"c": 0.0, "d": 1.0, "ofi_window_s": 30.0} | 0.2024 | 0.0620 | 0 | 8 |
| {"c": 0.0, "d": 0.5, "ofi_window_s": 5.0} | 0.0960 | 0.1110 | 0 | 10 |
| {"c": 0.5, "d": 0.0, "ofi_window_s": 1.0} | 0.0160 | -0.1259 | 0 | 13 |
| {"c": 0.0, "d": 1.0, "ofi_window_s": 5.0} | -0.0364 | 0.0199 | 0 | 7 |
| {"c": 0.5, "d": 0.0, "ofi_window_s": 30.0} | -0.0982 | -0.2021 | 0 | 16 |
| {"c": 0.5, "d": 0.5, "ofi_window_s": 30.0} | -0.1076 | -0.1761 | 0 | 10 |
| {"c": 0.5, "d": 0.0, "ofi_window_s": 5.0} | -0.1602 | -0.4701 | 0 | 14 |
| {"c": 0.5, "d": 1.0, "ofi_window_s": 5.0} | -0.2554 | -0.3692 | 0 | 11 |
| {"c": 0.5, "d": 0.5, "ofi_window_s": 5.0} | -0.2607 | -0.3640 | 0 | 12 |
| {"c": 0.5, "d": 1.0, "ofi_window_s": 30.0} | -0.3245 | -0.2464 | 0 | 9 |
| {"c": 1.0, "d": 1.0, "ofi_window_s": 1.0} | -0.4886 | -0.4856 | 0 | 32 |
| {"c": 1.0, "d": 0.5, "ofi_window_s": 5.0} | -0.5295 | -0.5827 | 0 | 70 |
| {"c": 1.0, "d": 0.5, "ofi_window_s": 1.0} | -0.5304 | -0.5941 | 0 | 64 |
| {"c": 1.0, "d": 1.0, "ofi_window_s": 5.0} | -0.5773 | -0.5758 | 0 | 27 |
| {"c": 1.0, "d": 0.5, "ofi_window_s": 30.0} | -0.6251 | -0.6787 | 0 | 73 |
| {"c": 1.0, "d": 0.0, "ofi_window_s": 1.0} | -0.7276 | -0.7924 | 0 | 766 |
| {"c": 1.0, "d": 1.0, "ofi_window_s": 30.0} | -0.7331 | -0.7720 | 0 | 30 |
| {"c": 1.0, "d": 0.0, "ofi_window_s": 5.0} | -0.7573 | -0.8032 | 0 | 1218 |
| {"c": 1.0, "d": 0.0, "ofi_window_s": 30.0} | -0.8056 | -0.8292 | 0 | 1500 |

Draft choice: {"c": 0.0, "d": 1.0, "ofi_window_s": 1.0}, mean daily BEF 0.8618 bp.

### B2b

| Candidate | Mean daily BEF bp | Pooled BEF bp | Days without fills | Median daily fills |
|---|---|---|---|---|
| {"c": 0.0, "d": 0.0, "tau_s": 30.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.0, "d": 0.0, "tau_s": 5.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.0, "d": 0.0, "tau_s": 1.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.5, "d": 0.0, "tau_s": 30.0} | 0.4733 | 0.3691 | 0 | 12 |
| {"c": 0.0, "d": 1.0, "tau_s": 1.0} | 0.4497 | 0.6021 | 0 | 7 |
| {"c": 0.0, "d": 1.0, "tau_s": 5.0} | 0.3908 | 0.6033 | 0 | 7 |
| {"c": 0.0, "d": 1.0, "tau_s": 30.0} | 0.3401 | 0.3918 | 0 | 9 |
| {"c": 0.5, "d": 1.0, "tau_s": 30.0} | 0.3031 | 0.1784 | 0 | 8 |
| {"c": 0.5, "d": 1.0, "tau_s": 5.0} | 0.2630 | 0.2769 | 0 | 8 |
| {"c": 0.5, "d": 0.0, "tau_s": 5.0} | 0.2428 | 0.1661 | 0 | 11 |
| {"c": 0.0, "d": 0.5, "tau_s": 1.0} | 0.2086 | 0.2891 | 0 | 8 |
| {"c": 0.0, "d": 0.5, "tau_s": 30.0} | 0.1886 | 0.2313 | 0 | 9 |
| {"c": 0.0, "d": 0.5, "tau_s": 5.0} | 0.1151 | 0.1845 | 0 | 8 |
| {"c": 0.5, "d": 0.5, "tau_s": 30.0} | 0.1138 | 0.0692 | 0 | 9 |
| {"c": 0.5, "d": 0.0, "tau_s": 1.0} | 0.0697 | -0.0643 | 0 | 12 |
| {"c": 1.0, "d": 0.0, "tau_s": 30.0} | 0.0471 | -0.1347 | 0 | 13 |
| {"c": 0.5, "d": 0.5, "tau_s": 5.0} | -0.0152 | 0.0199 | 0 | 10 |
| {"c": 1.0, "d": 0.5, "tau_s": 30.0} | -0.1184 | -0.2911 | 0 | 12 |
| {"c": 1.0, "d": 1.0, "tau_s": 30.0} | -0.1356 | -0.2580 | 0 | 8 |
| {"c": 0.5, "d": 0.5, "tau_s": 1.0} | -0.2135 | -0.2941 | 0 | 12 |
| {"c": 0.5, "d": 1.0, "tau_s": 1.0} | -0.2417 | -0.2666 | 0 | 9 |
| {"c": 1.0, "d": 0.5, "tau_s": 5.0} | -0.4845 | -0.6077 | 0 | 17 |
| {"c": 1.0, "d": 0.0, "tau_s": 5.0} | -0.4913 | -0.5428 | 0 | 21 |
| {"c": 1.0, "d": 1.0, "tau_s": 5.0} | -0.6225 | -0.6528 | 0 | 14 |
| {"c": 1.0, "d": 0.0, "tau_s": 1.0} | -0.7837 | -0.8125 | 0 | 138 |
| {"c": 1.0, "d": 0.5, "tau_s": 1.0} | -0.9036 | -0.9113 | 0 | 97 |
| {"c": 1.0, "d": 1.0, "tau_s": 1.0} | -0.9228 | -0.9221 | 0 | 88 |

Draft choice: {"c": 0.0, "d": 0.0, "tau_s": 1.0}, mean daily BEF 0.6605 bp, 3 candidates tied at the top.

### B3

| Candidate | Mean daily BEF bp | Pooled BEF bp | Days without fills | Median daily fills |
|---|---|---|---|---|
| {"c": 0.0, "d": 0.0} | 0.6605 | 0.4865 | 0 | 11 |
| {"c": 0.5, "d": 0.0} | 0.5708 | 0.5174 | 0 | 13 |
| {"c": 0.5, "d": 0.5} | 0.3112 | 0.3302 | 0 | 9 |
| {"c": 1.0, "d": 0.5} | 0.1835 | 0.1190 | 0 | 11 |
| {"c": 0.0, "d": 1.0} | 0.1615 | 0.2293 | 0 | 9 |
| {"c": 0.5, "d": 1.0} | 0.1098 | 0.2558 | 0 | 9 |
| {"c": 0.0, "d": 0.5} | 0.0390 | 0.0672 | 0 | 9 |
| {"c": 1.0, "d": 0.0} | 0.0317 | 0.0407 | 0 | 17 |
| {"c": 1.0, "d": 1.0} | -0.0003 | 0.0137 | 0 | 10 |

Draft choice: {"c": 0.0, "d": 0.0}, mean daily BEF 0.6605 bp.

## Minimum detectable effect (section 9)

s is the larger of the standard deviations of D_i = BEF_B3 - BEF_B2b with the draft
settings: on the training days (run c89d0cb8e412) and on the validation days
(run 9eaa1b3d693c). n = 16 test days.

| Quantity | Value |
|---|---|
| s on training days, bp | 0.0000 |
| s on validation days, bp | 0.0000 |
| s, bp | 0.0000 |
| MDE = 0.70 s, bp | 0.0000 |
| 3 x MDE (C2 threshold), bp | 0.0000 |

Limitation: B3 and B2b have the same BEF on every training and validation day under
this draft choice (both have c = d = 0 and so reduce to B1), so D_i = 0 by construction
and s, the MDE and the C2 threshold are 0 for that reason. They measure nothing about
noise, and H1 cannot be tested with this choice (Q47 in docs/SESSION_REPORT.md).

## Canaries on the validation days (section 10)

Run 9eaa1b3d693c (configs/runs/canaries_val_draft.yaml, commit 88f9b4a), primary cell;
C3 is B3 at zero latency in the risk-averse queue model.

| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |
|---|---|---|---|---|---|---|
| C1 - B1 (pass: interval includes 0), identical every day, so the verdict is trivial | 6 | 0.0000 | [0.0000, 0.0000] | [0.0000, 0.0000] | 0 | none |
| C1 - B3 (descriptive), identical every day, so the verdict is trivial | 6 | 0.0000 | [0.0000, 0.0000] | [0.0000, 0.0000] | 0 | none |
| C2 - B1 (pass: mean above 3 x MDE) | 6 | -0.8720 | [-1.7830, -0.0659] | [-2.1203, 0.3763] | 2 | none |
| C4_x0.1 - B3, identical every day, so the verdict is trivial | 6 | 0.0000 | [0.0000, 0.0000] | [0.0000, 0.0000] | 0 | none |
| C4_x10 - B3, identical every day, so the verdict is trivial | 6 | 0.0000 | [0.0000, 0.0000] | [0.0000, 0.0000] | 0 | none |

- AC4.2, C2 beats B1 by more than 3 x MDE: fails.
- AC4.3, the C1 interval against B1 includes 0: passes.
- C3, mean BEF of B3 by latency, bp: zero 0.8358, high 0.6605; flag (a non-zero latency above zero latency): False.
- C4, matches B3 within the interval: {'C4_x0.1': True, 'C4_x10': True}.

Statement from eval/analysis.canaries: C1, shuffled signs, did not differ detectably from B1. C2, the oracle, did not beat B1 by 3 times the MDE: the harness cannot convert information into PnL, and the study stops. C3, zero latency, was above B3 at every non-zero latency on the mean. C4_x0.1 matched B3 within the interval; C4_x10 matched B3 within the interval. So the fitted decay is not what drives any gain.
