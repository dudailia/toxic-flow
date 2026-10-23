# Hawkes fit on the training days, and diagnostics on the validation days

Written by scripts/hawkes_diagnostics.py from docs/signals/train_constants.json
(scripts/fit_signals.py) and docs/signals/hawkes_val_residuals.json. The fit pools
the 12 training days, each an independent realisation of one day, on
exchange timestamps of collapsed market-order events (PREREGISTRATION.md section 5).

## Fit

11,847,459 events. Log-likelihood 15711733.7. Converged: True.
Branching ratio (spectral radius of alpha / beta): 0.6702, which is below 1, so AC3.4 holds.

| Parameter | Estimate | Standard error |
|---|---|---|
| mu_b | 1.96791 | 0.00223 |
| mu_s | 1.87873 | 0.00218 |
| alpha_bb | 8.14889 | 0.0114 |
| alpha_bs | 1.01167 | 0.00373 |
| alpha_sb | 1.22331 | 0.00392 |
| alpha_ss | 8.12479 | 0.0115 |
| beta | 13.8014 | 0.0212 |

Units: mu and alpha per second, beta per second. alpha_kj is the jump in the
intensity of type k after an event of type j (b buyer-initiated, s seller-initiated).

Known limitation, stated in section 5: the baseline mu is constant over the day, so
intraday seasonality is left to the excitation, which tends to inflate the branching
ratio.

## Constants K (training days)

| Signal and parameter | K |
|---|---|
| B2b_ewma_1s | 3.450032 |
| B2b_ewma_5s | 2.649641 |
| B2b_ewma_30s | 2.142253 |
| B3_hawkes | 3.878084 |
| C4_x10 | 9.303423 |
| C4_x0.1 | 2.197368 |

C4_x10 and C4_x0.1 are the wrong-decay canaries, with their own K (Q25).

## Time-rescaling diagnostics on the validation days (AC3.5)

Under the fitted model each type's rescaled inter-event times are i.i.d. Exp(1):
mean 1, and a KS test against Exp(1) that does not reject. Reported whatever they show.

| Day | Type | Events | Mean | KS statistic | KS p-value |
|---|---|---|---|---|---|
| 2025-01-01 | b | 274,145 | 1.2845 | 0.1277 | 0 |
| 2025-01-01 | s | 276,304 | 1.2641 | 0.1194 | 0 |
| 2025-02-01 | b | 314,753 | 1.1989 | 0.1160 | 0 |
| 2025-02-01 | s | 293,028 | 1.2378 | 0.1131 | 0 |
| 2025-03-01 | b | 445,802 | 1.0423 | 0.0681 | 0 |
| 2025-03-01 | s | 428,868 | 1.0593 | 0.0679 | 0 |
| 2025-04-01 | b | 435,840 | 1.0592 | 0.0717 | 0 |
| 2025-04-01 | s | 467,490 | 1.0185 | 0.0604 | 0 |
| 2025-05-01 | b | 418,057 | 1.0748 | 0.0503 | 0 |
| 2025-05-01 | s | 443,109 | 1.0386 | 0.0574 | 0 |
| 2025-06-01 | b | 258,044 | 1.3194 | 0.1403 | 0 |
| 2025-06-01 | s | 246,631 | 1.3396 | 0.1518 | 0 |

Largest KS statistic: 0.1518. With hundreds of thousands of events per day the
KS test detects small departures, so the statistic is the more useful number; the
constant baseline is the expected source of misfit.

Mean residual from 1.019 to 1.340. A mean above 1 means the fitted model
expected more events than the day had, so the training fit runs hot on these days.

B2's K (OFI windows of 1, 5 and 30 s) is not computed: its input needs a replay of the
whole book per day, which this machine has neither the disk nor the memory to hold
(K_not_computed in train_constants.json: B2_ofi_1s, B2_ofi_5s, B2_ofi_30s).
