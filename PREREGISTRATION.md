# PREREGISTRATION: toxic-flow v1

Status: DRAFT. Frozen by the annotated git tag `prereg-v1`, which Ilia Duda creates and
pushes to the public GitHub remote. After the tag this file does not change. Deviations go in DEVIATIONS.md, and both the original and the
changed analysis are reported.

## Design history

Two designs exist. The tag prereg-v1 freezes the second one, v2.

v1 (drafted 2026-10-22 to 2026-10-24) used a fixed spread around the mid as B0, the GLFT
quoting model as B1, and an overlay that moved the GLFT quote centre by c u delta and
widened both quotes by d m delta. On the validation days v1 failed canary C2: the oracle
gained -0.872 bp a day over B1 (bootstrap [-1.783, -0.066]), so that design could not show
that information becomes PnL (docs/M4_draft.md). The diagnosis (docs/M4_diagnosis.md,
exploratory, training and validation days only) found no sign bug, and found that latency
and queue pessimism were not the cause. Its reasons, ranked:
1. Fills at the touch mark out at about -0.7 to -0.9 bp in every queue model and latency,
   while the one-tick spread is worth about 0.01 bp, so every strategy has a negative
   break-even fee before any fee is charged.
2. B1 at its selected setting quoted about 370 ticks from mid on training days and 860 on
   validation days, so it traded 146 and 14 times a day. GLFT works in ticks, and its
   quotes widen as the price rises.
3. With c = 1 the centre shift put one C2 quote at the touch about a quarter of the time,
   so C2 was not B1 plus information but a different quoting regime that inherited
   reason 1. On a join-the-touch base the same oracle beat its base on 12 of 12 training
   days.
4. Re-quoting at nearly every step the mid moves. Minor: a base that cancels half as
   often loses as much.

v2 was chosen on 2026-10-25 by Ilia Duda, after seeing these training and validation
diagnostics and before any test-day data was downloaded. It quotes at the touch and turns
a signal into stepping back on the side the signal marks as toxic. The v2 overlay mapping
had not been run on any day when this section was written. Unchanged from v1: the
question, data, simulation, the signal definitions, metrics, hypotheses, analysis, the MDE
rule and the pre-committed conclusions. Changed: section 4 (strategies and overlay),
section 5 (threshold constants added) and section 10 (canaries mapped to v2). GLFT is
reported as an exploratory result (docs/exploratory/glft.md), not as a strategy. The
v1 grid-edge and scoring-window rules for choosing B0 and B1 no longer apply, because v2
B0 and B1 have no parameters. Choosing a design after seeing validation results is a
degree of freedom of the researcher; it is disclosed here, and the test days stay unseen
until the tag.

The C1 pass rule was revised on 2026-10-26 by Ilia Duda, after seeing C1 fail against B1
on the validation days and before any test-day data was downloaded. As first written for
v2, C1 passed if the interval for C1 minus B1 included 0. On the validation days C1 lost
to B1 by 0.0090 bp a day (bootstrap [-0.0126, -0.0055], 0 of 6 days above 0;
docs/M4_v2_draft.md), so it failed. The leakage audit found no leak. It found that a
pulled quote rejoins at the back of the queue, so pulling costs queue position even when
the pull carries no information, and B1 never pulls; C1 minus B1 therefore mixes the cost
of pulling with any information in the signs. The revised rule judges C1 against R1, B1
with random pulls at C1's realised pull rate (section 10). The original C1 minus B1
result stays in the report beside the revised one. Revising a pass rule after seeing it
fail is a degree of freedom of the researcher, disclosed here.

## 1. Question

On Binance USDT-M BTCUSDT perpetual tick data, does a causal Hawkes estimate of
market-order intensity raise a passive market maker's edge per unit of traded notional,
out of sample, compared with the same quoting model without the signal and with two
cheaper order-flow signals?

The comparison that answers "is the Hawkes model decoration" is B3 against B2b. Both use
the same market-order events and the same idea of exponentially decaying memory. They
differ only in whether the excitation structure and decay are fitted by maximum
likelihood. If B3 does not beat B2b, the Hawkes fit added nothing beyond a weighted
trade count in this setup.

Expected, and not a finding: every strategy loses money at the standard retail maker
fee, because the BTCUSDT spread is usually one tick and one tick is a small fraction of a
basis point. That is why the primary metric does not depend on the fee.

## 2. Data

Source: Tardis.dev free first-day-of-month datasets, `incremental_book_L2` and `trades`,
exchange `binance-futures`, symbol `BTCUSDT`, one full UTC day per file.

| Split      | Dates                      | Days | Used for                                         |
|------------|----------------------------|------|--------------------------------------------------|
| train      | 2024-01-01 to 2024-12-01   | 12   | Hawkes fit, constant K, thresholds, B0 and B1 runs |
| validation | 2025-01-01 to 2025-06-01   | 6    | Overlay tuning, MDE estimate, canary checks      |
| test       | 2025-07-01 to 2026-10-01   | 16   | Confirmatory analysis, run once                  |

Exact dates are in configs/splits.yaml. Test-day files are not downloaded before the tag
exists on the public remote. Evidence: the tag's push time on GitHub, download
timestamps in data/manifest.json, and the split-lock tests.

Disclosure. During recon on 2026-10-22, before the tag, HEAD requests went to test-day
URLs: 64 recorded (32 in data/recon.json, 32 in data/recon_logs/) and at most 64 more
from two runs whose output was lost, so at most 128 in all. Every one returned HTTP 404
with no body; the server answers HEAD with 404 for every URL, including symbols that do
not exist, so the responses carried no information about the files. No GET was sent to
a test-day URL and no test-day byte was received. The runs are listed in
data/recon_logs/2026-10-22_recon_runs.txt.

Exclusion rules, applied by script before any strategy result for that day exists:
1. The Tardis file is missing: a GET of it returns HTTP 404 or 400 twice, at least 24
   hours apart. A 429, a 5xx or a network error never counts as missing; the downloader
   tries again on a later run. A HEAD response never counts.
2. hftbacktest conversion fails.
3. Either stream has a gap longer than 10 minutes inside the quoting window.

An excluded day is listed with its rule number. No other reason excludes a day.

## 3. Simulation

- Engine: hftbacktest 2.4.4, pinned in uv.lock. Replay-based, so our orders do not move
  the market. Order size is the minimum the venue allows, which keeps that assumption
  close to true.
- Exchange model: no partial fills (`no_partial_fill_exchange()`, the hftbacktest
  default). The partial-fill model stops with an internal error on 2024-01-01 in
  hftbacktest 2.4.4 (docs/ENGINE.md), so it cannot run the study. Limitation, stated next
  to results: an order at the front of the queue fills in full on any trade at its price,
  whatever the trade size, so fills made by prints smaller than our order are counted in
  full.
- Order size: smallest size meeting the minimum quantity and minimum notional for that
  date in configs/venue.yaml. Inventory cap Q = 10 order sizes.
- Decision step: every 100 ms of simulated time. Quotes are post-only limit orders,
  cancelled and replaced when the target price changes. The cancel and its replacement
  go out in the same step, identically for every strategy and canary. A replacement
  waits only while an earlier order on that side is unacknowledged, or while the
  inventory cap would not hold if every open order on that side filled, cancels in
  flight included.
- Day structure: estimators warm up from 00:00 to 00:30 UTC with no quoting. Quoting runs
  from 00:30:00 to 23:59:00 UTC. At 23:59:00 all orders are cancelled and inventory is
  marked at mid. There is no flattening trade.
- Mid: (best bid + best ask) / 2 from the simulator's book.
- Queue models, all reported: risk-averse (position advances only on trades; the
  pessimistic reference), probabilistic with power function n = 3, power n = 2, and
  log function. Exact API names in hftbacktest 2.4.4: `risk_adverse_queue_model()`,
  `power_prob_queue_model(3.0)`, `power_prob_queue_model(2.0)` and `log_prob_queue_model()`. The fill-count ordering on training days is
  reported.
- Latency, both reported: low sets order entry and response latency from the day's
  observed feed latency (local timestamp minus exchange timestamp), sampled once per
  second of local time by hftbacktest's `generate_order_latency` with multiplier 1 for
  entry and response, and loaded with `intp_order_latency`. Order latency at time t is
  interpolated between the samples on either side of t, so it uses feed latency up to
  one second ahead; the strategy never reads latency, so this cannot inform a decision.
  High is three times low and stands for a slower participant without co-location.
  Zero latency runs only as canary C3.
- Fees: simulated at zero and applied in evaluation as fee rate times traded notional.
  This is exact because no strategy conditions on fees. A test checks it against
  hftbacktest's own fee model on one day.
- Funding payments are not modelled. Inventory at each 8-hour funding time is reported
  so the omission can be bounded.

Primary cell: risk-averse queue model, high latency.

## 4. Strategies

All strategies use the same engine, order size, inventory cap, latency and queue settings,
and at most one order per side (section 3). Prices are in ticks and q is inventory in
order sizes.

- B0, join the touch: bid at the best bid, ask at the best ask, no skew.
- B1, join the touch with inventory skew: bid = best bid - q, ask = best ask - q, so each
  order size of inventory moves both quotes one tick against the position.
- B2 = B1 + overlay driven by order-flow imbalance.
- B2b = B1 + overlay driven by signed decay-weighted trade counts.
- B3 = B1 + overlay driven by the bivariate Hawkes intensity.

For every strategy, a bid at or above the best ask moves to the best ask minus one tick,
and the mirror rule applies to the ask. No bid is quoted when q >= Q and no ask when
q <= -Q. B0 and B1 have no free parameters, so nothing is chosen for them; they are run on
the training days in all 8 cells and reported. GLFT, the v1 B1, is reported as an
exploratory result in docs/exploratory/glft.md and is not a strategy of this study.

Overlay, identical for B2, B2b and B3, with direction u in [-1, 1] and magnitude m in [0, 1]
from section 5, and three settings: pull rate p, step K and the magnitude rule.

    toxic side: the ask when u > theta_u(p), the bid when u < -theta_u(p), else none
    the toxic side steps back K ticks (ask + K or bid - K), or is not quoted when K = pull
    magnitude rule on: when m > theta_m, both sides step back one more tick

u > 0 says buyers are arriving, which tends to come before a rise in the mid, so a resting
ask is the quote that would be filled just before the price moves against it; the mirror
holds for u < 0. theta_u(p) is the (1 - p) quantile of |u| on training days for that
signal and parameter, so the toxic side steps back on a share p of the training-day
decision steps; theta_m is the 90th percentile of m on training days (section 5). The steps
add: with K = 5 ticks and the magnitude rule on, the toxic side moves 6 ticks back and the
other side 1. The step is applied to the B1 quote, then the cross rule and the cap apply.

Tuning grids for overlays, on validation days in the primary cell:
- p in {5%, 10%, 25%, 50%} of decision steps, K in {1 tick, 5 ticks, pull the side}, and
  the magnitude rule off or on: 24 combinations, the same for every signal and setting.
- B2: OFI window W in {1 s, 5 s, 30 s}. 72 candidates.
- B2b: decay tau in {1 s, 5 s, 30 s}. 72 candidates.
- B3: fitted beta, no extra parameter. 24 candidates.

B3 gets fewer candidates than its rivals, which makes a B3 win harder, not easier.
Selection: maximise the mean daily break-even fee over validation days; ties go to the
smaller p, then the smaller K (1 tick, 5 ticks, pull), then the magnitude rule off, then
the shorter window or decay. Every candidate has p above 0, so none equals B1; whether
an overlay helps at all is H3 and H4 (section 7). Selected settings (configs/selected.yaml, from runs 0bd4181a312a and 9e93e4415b6b,
docs/M4_v2_draft.md): B2 with W = 5 s at p = 25%; B2b with tau = 5 s at p = 25%; B3 at
p = 5%. All three pull the toxic side and have the magnitude rule off.

## 5. Signals

Market-order events: trades with the same exchange timestamp and the same aggressor side
collapse into one event. Side b means buyer-initiated, s means seller-initiated. At
decision time t the strategy sees only events whose local timestamp is at or before t.

B2b, signed decay-weighted counts:

    E_b(t) = sum over buy events i with local_ts_i <= t of exp(-(t - local_ts_i) / tau)
    E_s(t) = same over sell events
    u = (E_b - E_s) / (E_b + E_s),   u = 0 when both are 0
    a = E_b + E_s

B3, bivariate Hawkes with exponential kernel and shared decay:

    lambda_k(t) = mu_k + sum over j in {b, s} and events i of type j with local_ts_i <= t
                  of alpha_kj * exp(-beta * (t - local_ts_i))
    u = (lambda_b - lambda_s) / (lambda_b + lambda_s)
    a = lambda_b + lambda_s

B2, best-level order-flow imbalance (Cont, Kukanov and Stoikov 2014):

    e_n = per-update OFI contribution at the best bid and ask
    OFI_W(t) = sum of e_n over updates with local_ts in (t - W, t]
    u = tanh(OFI_W(t) / s_W(t)),  s_W(t) = trailing 30-minute standard deviation of OFI_W
    a = |OFI_W(t)|

Magnitude, same rule for all three:

    m(t) = clip((a(t) / abar(t) - 1) / K, 0, 1)

where abar(t) is the trailing 30-minute mean of a at decision steps and K is the 99th
percentile of (a / abar - 1) on training days for that signal and parameter. Trailing
normalisers keep the signal on the same scale when volume levels differ between 2024
and 2026. Constants K, from the 12 training days (docs/hawkes_fit.md): B2 7.165, 4.664
and 3.423 for W = 1, 5 and 30 s; B2b 3.450, 2.650 and 2.142 for tau = 1, 5 and 30 s; B3
3.878; C4 9.303 (beta times 10) and 2.197 (beta divided by 10).

Thresholds for the overlay (section 4), from the 12 training days, for every signal and
parameter of the tuning grid and for the two C4 decays: theta_u(p) is the (1 - p) quantile
of |u| over every decision step of the quoting windows (00:30:00 to 23:59:00 UTC) of the
training days pooled, for p in {0.05, 0.10, 0.25, 0.50}, and theta_m is the 0.90 quantile
of m over the same steps. Like K, they are fixed numbers computed once. A test checks
that the share of training-day steps with |u| > theta_u(p) is within 1 percentage point
of p. Values, rounded to 4 decimals here; the runs use the full values in
docs/signals/train_thresholds.json (SHA-256 c9fa1ce13f94a49e7a1fc2e8381c32aee5efaf80c4efa24f9f5a94eacc88f5dd),
which every run config copies:

| Signal setting | theta_u at p 5% | 10% | 25% | 50% | theta_m |
|---|---|---|---|---|---|
| B2_ofi_1s | 0.9764 | 0.9107 | 0.5848 | 0.1768 | 0.2477 |
| B2_ofi_5s | 0.9749 | 0.9282 | 0.7320 | 0.3722 | 0.3190 |
| B2_ofi_30s | 0.9732 | 0.9339 | 0.7875 | 0.5082 | 0.3632 |
| B2b_ewma_1s | 0.8562 | 0.7561 | 0.5614 | 0.3415 | 0.2401 |
| B2b_ewma_5s | 0.6463 | 0.5597 | 0.4045 | 0.2398 | 0.2482 |
| B2b_ewma_30s | 0.4801 | 0.3958 | 0.2718 | 0.1569 | 0.2542 |
| B3_hawkes | 0.5693 | 0.5142 | 0.3901 | 0.1851 | 0.2184 |
| C4_x10 | 0.6897 | 0.6014 | 0.0933 | 0.0232 | 0.0992 |
| C4_x0.1 | 0.3932 | 0.3308 | 0.2325 | 0.1367 | 0.2308 |

Pooled over the training days, every setting's share of steps with |u| above theta_u(p)
is p to within 0.0001, and the share with m above theta_m is 10%, except C4 at beta x 10
at p = 50%: 46.0%, because its intensity returns to the baseline between events and |u|
ties there. B3 is selected at p = 5%, so that tie affects no run of the study.

Hawkes fit: parameters mu_b, mu_s, alpha_bb, alpha_bs, alpha_sb, alpha_ss, beta, by
maximum likelihood pooled over the 12 training days, each day an independent
realisation, on exchange timestamps of collapsed events. The spectral radius of the
matrix alpha / beta must be below 1; if not, the study stops and this section is revised
before the tag. Time-rescaling residuals and KS statistics on validation days are
reported whatever they show. Fitted values with standard errors, from 11,847,459 events
on the 12 training days (docs/hawkes_fit.md): mu_b 1.968 (0.002), mu_s 1.879 (0.002),
alpha_bb 8.149 (0.011), alpha_bs 1.012 (0.004), alpha_sb 1.223 (0.004), alpha_ss 8.125
(0.012), beta 13.80 (0.02), all per second; branching ratio 0.670.

Known limitation, stated now: a constant baseline mu ignores intraday seasonality, which
tends to inflate the fitted branching ratio.

## 6. Metrics

For strategy s on day i, over the quoting window:

- Gross PnL G_si (USDT) = change in cash + change in inventory times mid, fees excluded.
- Traded notional N_si (USDT) = sum over fills of |quantity * price|.
- Break-even maker fee, primary: BEF_si = 10,000 * G_si / N_si, in basis points. It is the
  maker fee at which the day's net PnL would be zero.
- Net PnL at fee f: G_si - f * N_si / 10,000, for f in {standard maker fee for that date,
  0, -0.1 bp}. -0.1 bp is the Tier 1 maker fee of Binance's USD-M Futures Liquidity
  Provider Program on USDT pairs, published for 2025-03-03 onward and open to accounts
  with at least 100M USD of 30-day futures volume (docs/DATA_RECON.md; source:
  https://www.binance.com/en/support/announcement/detail/cde392fe431a4045a951d40d7498abbc).
  It applies to the test days. For training and validation days before 2025-03-03 it is
  a hypothetical rate.
- Markouts: for each fill, 10,000 * side * (mid(t_fill + h) - p_fill) / p_fill, side = +1
  for a buy, h in {1 s, 10 s, 60 s}. Negative means adverse selection.
- Inventory variance: variance of q sampled each second, in order-size units.
- Fill rate: fills per quoting hour. Quote presence: share of time both sides are quoted.

## 7. Hypotheses

H1, confirmatory: in the primary cell, the mean over test days of
D_i = BEF_B3,i - BEF_B2b,i is not zero. Two-sided.

Exploratory, same statistic, reported with intervals and labelled exploratory:
- H2: B3 against B2 (Hawkes against OFI).
- H3: B3 against B1 (does the overlay help at all).
- H4: B2b against B1 (does the cheap signal help at all).
- B3 against R_B3 and B2b against R_B2b: each selected overlay against B1 with random
  pulls at that overlay's own realised pull rate on each day (section 10), 3 seeds, the
  control's day value being the mean over seeds. These separate what the signal chooses
  from what pulling at that rate costs by itself. The random pulls start more runs of a
  pulled side than the signals do, so these comparisons overstate the signal's part;
  that is stated with them.
- Markout differences for the same pairs at each horizon.

## 8. Analysis

- Paired day-level bootstrap: 10,000 resamples of test days, seed 1729, 95% percentile
  interval for the mean of D_i.
- Sensitivity: paired t interval. With 16 days the percentile bootstrap tends to be too
  narrow. If the two intervals disagree on whether 0 is inside, the result is reported
  as inconclusive.
- A day where either strategy has zero fills is dropped from that pair and reported.
- H1 holds if and only if (a) both intervals exclude 0 in the primary cell and (b) the point
  estimate has the same sign in all 8 queue and latency cells.
- Descriptive: the number of test days with D_i > 0, and a per-day plot of D_i.
- Selectivity check: ratio of B3 to B2b traded notional on the median test day. If it is
  below 0.5, the conclusion states that B3 traded less than half as much, and any effect
  is labelled as selectivity rather than better pricing.
- Markout intervals use the same day-level bootstrap, with fills grouped by day.

## 9. Minimum detectable effect

    MDE = (z_0.975 + z_0.80) * s / sqrt(n) = 2.80 * s / 4 = 0.70 * s,   n = 16

s is the larger of two estimates of the standard deviation of D_i with the selected
settings: one on the 6 validation days and one on the 12 training days. Taking the
larger is deliberate; 6 days give a noisy estimate.

With the selected settings: s = 0.0329 bp on the 12 training days (run 58c46cc49981)
and 0.0313 bp on the 6 validation days (run 5d27bc8ae820), so s = 0.0329 bp and
MDE = 0.70 s = 0.0231 bp (docs/M4_v2_draft.md). C2's threshold, 3 x MDE, is 0.0692 bp.

If excluded test days reduce n, the MDE is recomputed with the same s and reported.
An effect smaller than the MDE is described as one this study could not detect, never as
absent.

## 10. Canaries

Run in the primary cell. Pass criteria on validation days must hold before the tag.

- C1, shuffled signs: B3 with the selected settings and B3's thresholds, but the side of
  each market-order event is randomly permuted within the day before it enters the
  intensity (seed 1729), so C1 steps back on a side that carries no order-flow
  information. Shuffling breaks the runs of same-side orders, so C1 marks a side toxic on
  fewer steps than B3. Its control is R1: B1 that, at each decision step independently,
  marks a side toxic with probability r and steps that side back by B3's K, the side
  chosen at random with equal chance, where r is C1's realised share of quoting steps
  with a side marked toxic on that day. R1 reads no market data. It runs with 3 seeds,
  and R1's value on a day is the mean over the seeds. Pass: the interval for C1 minus R1
  includes 0 (revised 2026-10-26, Design history). C1 minus B1, the rule first written,
  and C1 minus B3 are reported beside it as descriptive.
- R_B3 and R_B2b, exploratory: R1's rule at B3's and at B2b's realised pull rate on each
  day, 3 seeds each, in the primary cell. B3 minus R_B3 and B2b minus R_B2b are reported
  as exploratory comparisons (section 7), with no pass rule. On test days each R runs
  after the strategy whose rate it takes, since the rate is that run's realised share.
- C2, oracle: B1 with the toxic side set by the future. The ask is not quoted while the mid
  5 s ahead is at least one tick above the mid now, and the bid is not quoted while it is
  at least one tick below; no magnitude rule. The only strategy allowed to see the future.
  Pass: the mean gain over B1 on validation days is larger than 3 times the MDE. If C2
  fails, the harness cannot convert information into PnL, and the study stops.
- C3, zero latency: B3 selected settings at zero latency. Reported as an upper bound.
  Flag if any non-zero-latency run of B3 beats it on the mean.
- C4, wrong decay: B3 at its selected p, K and magnitude rule, with beta multiplied by 10
  and divided by 10, alpha rescaled so the branching ratio stays at its fitted value, and
  K, theta_u(p) and theta_m computed on training days for each variant by the section 5
  rules, since each is a different parameter setting. Reported. If either variant matches
  B3 within the interval, the conclusion says the fitted decay is not what drives any gain.

On test days all canaries are reported in full whatever they show.

## 11. Pre-committed conclusions

| Outcome on test days                                        | Statement in the paper |
|-------------------------------------------------------------|------------------------|
| H1 holds, D > 0                                             | The fitted Hawkes overlay added X bp of edge per unit of notional over a decay-weighted trade count, with interval [L, U], in every queue and latency cell. |
| Intervals include 0 and abs(mean D) < MDE                   | No detectable difference between the Hawkes overlay and a decay-weighted trade count. The study could detect effects of MDE bp or larger. |
| Intervals include 0 and abs(mean D) >= MDE                  | Inconclusive: the point estimate is large but the test set is too small to separate it from noise. |
| Primary intervals exclude 0 but the sign flips in some cell | Does not hold. The result depends on the queue or latency model. |
| H1 holds, D < 0                                             | The Hawkes overlay did worse than a decay-weighted trade count by X bp, interval [L, U]. |
| C1 fails on test days                                       | The signal's gain does not depend on event signs, so it is not order-flow information. Primary result reported but not interpreted. |

A negative or null result is a valid outcome and is published as such.

## 12. Deviations

Any change after the tag goes in DEVIATIONS.md with the date, what changed, why, and
which results it affects. Both the pre-registered and the changed analysis are reported.
Bug fixes count as deviations.
