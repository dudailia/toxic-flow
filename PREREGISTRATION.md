# PREREGISTRATION: toxic-flow v1

Status: DRAFT. Frozen by the annotated git tag `prereg-v1`, which Ilia Duda creates and
pushes to the public GitHub remote after every [TBD] below is resolved. After the tag this
file does not change. Deviations go in DEVIATIONS.md, and both the original and the
changed analysis are reported.

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
| train      | 2024-01-01 to 2024-12-01   | 12   | Hawkes fit, B0 and B1 parameters, constant K     |
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
- Exchange model: [TBD M0: partial-fill or no-partial-fill, with reason].
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
  log function. Exact API names: [TBD M0]. The fill-count ordering on training days is
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

All strategies use the same engine, order size, inventory cap, latency and queue settings.

- B0, fixed spread: bid = mid - h ticks, ask = mid + h ticks, h in {1, 2, 3, 5}.
- B1, GLFT: closed-form approximation of Gueant, Lehalle and Fernandez-Tapia (2013) as
  in the hftbacktest GLFT tutorial. Reservation price r = mid - skew * q, half-spread
  delta. Arrival parameters A and k and volatility sigma are estimated over a trailing
  window. Risk aversion gamma and the window length are chosen on training days.
- B2 = B1 + overlay driven by order-flow imbalance.
- B2b = B1 + overlay driven by signed decay-weighted trade counts.
- B3 = B1 + overlay driven by the bivariate Hawkes intensity.

Overlay, identical for B2, B2b and B3, with direction u in [-1, 1] and magnitude m in [0, 1]
from section 5:

    centre = r + c * u * delta
    bid    = centre - delta * (1 + d * m)
    ask    = centre + delta * (1 + d * m)

Prices are rounded outward to the tick (bid down, ask up). A bid at or above the best ask
moves to best ask minus one tick, and the mirror rule applies to the ask. No bid is
quoted when q >= Q and no ask when q <= -Q. With c = d = 0 every overlay reduces to B1.

Choosing B0 and B1 parameters, on training days in the primary cell: maximise the mean
daily break-even fee. B0 grid: h in {1, 2, 3, 5}. B1 grid, 12 combinations: gamma in
{0.025, 0.05, 0.1, 0.2} and estimation window in {5, 10, 20} minutes, with A and k
refitted every 5 s. The hftbacktest GLFT tutorial uses gamma = 0.05, which it calls
arbitrarily chosen, and a 10-minute window; the grid spans factors of two around both,
and every window fits inside the 30-minute warm-up. Chosen values: [TBD M2].

Tuning grids for overlays, on validation days in the primary cell:
- c in {0, 0.5, 1} and d in {0, 0.5, 1} for all three.
- B2: OFI window W in {1 s, 5 s, 30 s}. 27 candidates.
- B2b: decay tau in {1 s, 5 s, 30 s}. 27 candidates.
- B3: fitted beta, no extra parameter. 9 candidates.

B3 gets fewer candidates than its rivals, which makes a B3 win harder, not easier.
Selection: maximise the mean daily break-even fee over validation days; ties go to the
smaller c + d, then the shorter window or decay. Selected settings: [TBD M4].

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
  0, [TBD M0: a published rebate tier with source, or a labelled hypothetical]}.
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

s = [TBD M4] bp. MDE = [TBD M4] bp.

If excluded test days reduce n, the MDE is recomputed with the same s and reported.
An effect smaller than the MDE is described as one this study could not detect, never as
absent.

## 10. Canaries

Run in the primary cell. Pass criteria on validation days must hold before the tag.

- C1, shuffled signs: B3 with the selected settings, but the side of each market-order
  event is randomly permuted within the day before it enters the intensity. Pass: the
  interval for C1 minus B1 includes 0. C1 minus B3 is reported beside it as
  descriptive.
- C2, oracle: B1 overlay with u = sign of the mid change over the next 5 s and m = 0, c = 1.
  The only strategy allowed to see the future. Pass: mean gain over B1 is larger than
  3 times the MDE. If C2 fails, the harness cannot convert information into PnL, and the
  study stops.
- C3, zero latency: B3 selected settings at zero latency. Reported as an upper bound.
  Flag if any non-zero-latency run of B3 beats it on the mean.
- C4, wrong decay: B3 with beta multiplied by 10 and divided by 10, alpha rescaled so the
  branching ratio stays at its fitted value, and K computed on training days for each
  variant by the section 5 rule, since each is a different parameter setting. Reported. If either variant matches B3
  within the interval, the conclusion says the fitted decay is not what drives any gain.

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
