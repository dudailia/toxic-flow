# Do the signals carry information? (exploratory, items 6 to 8)

Exploratory, before any quoting: no strategy, fill or fee enters. For every signal and
parameter setting of the section 4 grid, plus the two C4 decays, the causal direction u(t)
and magnitude m(t) at each 100 ms decision time in the quoting window are compared with
the mid change over the next 1, 5 and 10 s: corr(u, dmid) for direction (item 6) and
corr(m, |dmid|) for magnitude, which is what widening needs (item 7). One Pearson
correlation per day; the tables give the mean over days with the day bootstrap of section 8
(10,000 resamples, seed 1729) and the days above 0. Measured on the 12 training days, then
checked on the 6 validation days out of sample; nothing was tuned here.

Code: src/toxic_flow/eval/signal_info.py (forward-looking, so in eval only), using the same
offline signal functions the overlay loop is tested against; scripts/signal_info.py. All
numbers: docs/exploratory/signal_information.json. Inputs: each day's 100 ms mid saved by
the diagnosis runs results/a582f2864e78 (training) and results/4de702fe5d20 (validation),
the market-order event tables, the OFI contributions and docs/signals/train_constants.json.

Limitation: correlation with the next mid change is a measure of information, not of
profit. A signal can predict a 1-tick move well and still not pay for a 0.9 bp adverse
selection (docs/M4_diagnosis.md).

## Direction: corr(u, mid change ahead), mean over days [bootstrap 95%]

| Signal | Train 1 s | Train 5 s | Train 10 s | Val 1 s | Val 5 s | Val 10 s |
|---|---|---|---|---|---|---|
| OFI, W 1 s | 0.177 [0.160, 0.193] | 0.137 [0.119, 0.154] | 0.109 [0.094, 0.124] | 0.193 [0.180, 0.207] | 0.152 [0.129, 0.174] | 0.118 [0.098, 0.140] |
| OFI, W 5 s | 0.115 [0.100, 0.129] | 0.107 [0.085, 0.130] | 0.092 [0.071, 0.115] | 0.137 [0.116, 0.157] | 0.128 [0.100, 0.157] | 0.104 [0.077, 0.132] |
| OFI, W 30 s | 0.047 [0.040, 0.054] | 0.050 [0.037, 0.063] | 0.045 [0.032, 0.059] | 0.057 [0.045, 0.069] | 0.059 [0.040, 0.078] | 0.052 [0.032, 0.074] |
| EWMA, tau 1 s | 0.104 [0.095, 0.113] | 0.087 [0.076, 0.098] | 0.075 [0.063, 0.087] | 0.112 [0.097, 0.127] | 0.094 [0.076, 0.112] | 0.077 [0.060, 0.096] |
| EWMA, tau 5 s | 0.068 [0.060, 0.076] | 0.066 [0.055, 0.079] | 0.059 [0.046, 0.075] | 0.079 [0.065, 0.093] | 0.074 [0.055, 0.096] | 0.064 [0.043, 0.086] |
| EWMA, tau 30 s | 0.027 [0.022, 0.032] | 0.029 [0.020, 0.038] | 0.026 [0.016, 0.038] | 0.031 [0.022, 0.040] | 0.031 [0.017, 0.045] | 0.027 [0.011, 0.043] |
| Hawkes, fitted beta | 0.116 [0.108, 0.124] | 0.074 [0.070, 0.079] | 0.059 [0.054, 0.064] | 0.120 [0.111, 0.130] | 0.076 [0.067, 0.084] | 0.058 [0.050, 0.067] |
| Hawkes, beta x 0.1 (C4) | 0.130 [0.119, 0.140] | 0.101 [0.088, 0.113] | 0.084 [0.071, 0.098] | 0.145 [0.128, 0.161] | 0.110 [0.090, 0.132] | 0.089 [0.069, 0.110] |
| Hawkes, beta x 10 (C4) | 0.094 [0.087, 0.099] | 0.052 [0.050, 0.054] | 0.039 [0.037, 0.042] | 0.093 [0.088, 0.100] | 0.051 [0.047, 0.055] | 0.037 [0.033, 0.041] |

Every direction correlation is above 0 on every training day (12 of 12) and on every
validation day but one (EWMA 30 s at 10 s, 5 of 6).

## Magnitude: corr(m, |mid change ahead|), mean over days [bootstrap 95%]

| Signal | Train 1 s | Train 5 s | Train 10 s | Val 1 s | Val 5 s | Val 10 s |
|---|---|---|---|---|---|---|
| OFI, W 1 s | 0.072 [0.058, 0.086] | 0.055 [0.038, 0.073] | 0.041 [0.026, 0.059] | 0.111 [0.089, 0.133] | 0.079 [0.058, 0.100] | 0.060 [0.041, 0.078] |
| OFI, W 5 s | 0.059 [0.046, 0.072] | 0.059 [0.042, 0.077] | 0.049 [0.033, 0.067] | 0.086 [0.066, 0.105] | 0.080 [0.058, 0.102] | 0.066 [0.046, 0.085] |
| OFI, W 30 s | 0.053 [0.046, 0.061] | 0.062 [0.051, 0.074] | 0.058 [0.045, 0.072] | 0.062 [0.045, 0.079] | 0.071 [0.050, 0.093] | 0.067 [0.047, 0.088] |
| EWMA, tau 1 s | 0.182 [0.167, 0.198] | 0.161 [0.147, 0.177] | 0.145 [0.131, 0.160] | 0.182 [0.165, 0.199] | 0.151 [0.132, 0.167] | 0.130 [0.112, 0.147] |
| EWMA, tau 5 s | 0.189 [0.173, 0.207] | 0.191 [0.176, 0.208] | 0.180 [0.165, 0.197] | 0.166 [0.152, 0.182] | 0.167 [0.149, 0.184] | 0.153 [0.134, 0.172] |
| EWMA, tau 30 s | 0.191 [0.172, 0.212] | 0.211 [0.193, 0.231] | 0.207 [0.189, 0.228] | 0.143 [0.129, 0.159] | 0.162 [0.146, 0.179] | 0.157 [0.138, 0.175] |
| Hawkes, fitted beta | 0.180 [0.167, 0.193] | 0.125 [0.114, 0.138] | 0.105 [0.094, 0.117] | 0.194 [0.181, 0.207] | 0.122 [0.108, 0.132] | 0.096 [0.085, 0.106] |
| Hawkes, beta x 0.1 (C4) | 0.205 [0.188, 0.223] | 0.181 [0.165, 0.198] | 0.163 [0.149, 0.180] | 0.206 [0.193, 0.220] | 0.170 [0.154, 0.182] | 0.146 [0.132, 0.160] |
| Hawkes, beta x 10 (C4) | 0.112 [0.103, 0.120] | 0.072 [0.064, 0.079] | 0.059 [0.053, 0.065] | 0.114 [0.107, 0.122] | 0.068 [0.062, 0.073] | 0.054 [0.050, 0.058] |

## Hawkes (fitted beta) minus EWMA, direction, per day [bootstrap 95%, days above 0]

| EWMA decay | Train 1 s | Train 5 s | Train 10 s | Val 1 s | Val 5 s | Val 10 s |
|---|---|---|---|---|---|---|
| tau 1 s | +0.012 [0.004, 0.020], 10/12 | -0.013 [-0.020, -0.005], 3/12 | -0.016 [-0.024, -0.009], 2/12 | +0.008 [-0.003, 0.019], 5/6 | -0.018 [-0.029, -0.007], 1/6 | -0.019 [-0.030, -0.009], 1/6 |
| tau 5 s | +0.048 [0.036, 0.060], 12/12 | +0.008 [-0.002, 0.018], 8/12 | -0.001 [-0.011, 0.009], 8/12 | +0.042 [0.027, 0.057], 6/6 | +0.002 [-0.013, 0.016], 3/6 | -0.006 [-0.020, 0.009], 2/6 |
| tau 30 s | +0.090 [0.078, 0.099], 12/12 | +0.046 [0.039, 0.053], 12/12 | +0.033 [0.025, 0.040], 12/12 | +0.089 [0.077, 0.102], 6/6 | +0.045 [0.035, 0.054], 6/6 | +0.031 [0.021, 0.041], 6/6 |

## What this says (item 8)

- Which signal predicts best: for direction, OFI over 1 s, at every horizon and in both
  splits (about 0.18 at 1 s, 0.14 at 5 s on training days). For magnitude, the EWMA counts
  and the slow-decay Hawkes (beta x 0.1) are about three times better than OFI's |OFI|,
  near 0.18 to 0.21.
- Hawkes against EWMA, before any quoting: mixed. The fitted Hawkes beats the 1 s EWMA on
  direction only at the 1 s horizon (+0.012, 10 of 12 days) and loses to it at 5 and
  10 s; it beats the 5 s and 30 s decays. The comparison that matters for H1 depends on
  which tau B2b gets, so this does not favour Hawkes in general.
- The fitted decay is not the most informative: the slower C4 variant (beta x 0.1) beats
  the fitted Hawkes on direction and magnitude at every horizon in both splits. This bears
  on C4's role in section 10, which reads "matches B3" as "the fitted decay is not what
  drives any gain".
- Train to validation: the direction results hold on the validation days, with the same
  ordering of signals and correlations within about 0.03. Magnitude levels move more, by
  up to about 0.05, and the lead of the 30 s EWMA at 5 and 10 s in training does not hold
  on validation, where the slow-decay Hawkes and the 5 s EWMA are level with it. The
  direction information is stable out of sample.
- The signals do carry information. Combined with docs/M4_diagnosis.md, the problem is
  not the signals but turning a correlation of 0.1 to 0.2 on the next few ticks into PnL
  against about 0.9 bp of adverse selection at the touch.
