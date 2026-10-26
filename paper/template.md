# Does a Hawkes model of order flow help a market maker? A pre-registered test

Independent work · 2026 · historical Binance data, simulated fills

A market maker that quotes at the touch on Binance BTCUSDT perpetual futures is, on
average, filled just before the price moves against it. This study asks whether a fitted Hawkes model of market orders tells
it when to step back better than a plain decay-weighted trade count does. The hypotheses,
settings and analysis were committed and tagged before any test day was downloaded. Every
result here comes from a replay simulation of historical data: no order was sent to an
exchange, and nothing here is a claim about live trading or profit.

## What the study asks

On {{pre_n_test}} test days, does a causal Hawkes estimate of market-order intensity raise
a passive market maker's edge per unit of traded notional, compared with the same quoting
rule driven by a decay-weighted count of the same market orders? The two signals use the
same events and the same idea of a memory that fades; they differ only in whether the
excitation and decay are fitted by maximum likelihood. If the Hawkes version does not do
better, the fit added nothing beyond a weighted trade count in this setup.

The edge is measured as the break-even maker fee (BEF): gross PnL divided by traded
notional, in basis points. It is the fee at which a day's net PnL would be zero, so it does
not depend on which fee tier one assumes. Every strategy here is expected to lose money at
the standard maker fee ({{pre_maker_fee}} bp on the training and validation days), because
the BTCUSDT spread is usually one tick, {{pre_tick}} USDT, a small fraction of a basis
point. That is not a finding.

The plan is in PREREGISTRATION.md, frozen by the git tag prereg-v1 on
{{prereg_tagged_at}}. Changes after the tag go to DEVIATIONS.md, and both the planned and
the changed analysis are reported.

## Data

Tardis.dev incremental order book (L2) and trade files for Binance USD-M futures,
BTCUSDT, one full UTC day per file, on the first day of each month:
{{pre_n_train}} training days (2024-01-01 to 2024-12-01), {{pre_n_val}} validation days
(2025-01-01 to 2025-06-01) and {{pre_n_test}} test days (2025-07-01 to 2026-10-01). Raw
files are pinned by SHA-256 in data/manifest.json. A day is excluded only by one of three
pre-registered rules (file missing, conversion fails, a gap over 10 minutes), applied by
script before any strategy result for that day exists.

The test days were not downloaded before the tag. A loader refuses a test date until the
tag exists on the public remote, and tests check that it does. One disclosure: during
recon, before the tag, at most 128 HEAD requests went to test-day URLs. Every one returned
HTTP 404 with no body, as the server does for any URL, so no test-day byte was received.

Market orders are trades with the same exchange timestamp and aggressor side, collapsed
into one event. The Hawkes model was fitted on {{pre_hawkes_events}} such events from the
training days.

Limitation: first-of-month days are a sample, not a continuous record, and the test days
cover a later and different market (the mid was {{pre_mid_first_train}} USDT on the first
training day and {{pre_mid_val_lo}} to {{pre_mid_val_hi}} on the validation days).

## How the market maker quotes

Simulation. hftbacktest {{hftbacktest_version}} replays the book and trades; our orders do
not move the market, which stays close to true because every order is the venue's minimum
size (at least {{pre_min_notional}} USDT notional). Decisions are made every 100 ms of
simulated time from 00:30 to 23:59 UTC, after a 30-minute warm-up; at 23:59 all orders are
cancelled and inventory is marked at mid. Quotes are post-only limit orders, at most one a
side, and inventory is capped at 10 order sizes. Fees are zero in the simulation and
applied afterwards, which is exact because no strategy reacts to fees.

Queue position is not observed in L2 data, so every result is computed under four queue
models (risk-averse, where an order moves up only when trades print at its price, and
three probabilistic models) and two latency settings (latency taken from the day's feed
delay, and three times that). The primary cell is the most pessimistic one: risk-averse
queue, high latency. A result that holds only under the optimistic models is reported as
not holding.

Strategies. All five share the engine, order size, cap and latency.

- B0 joins the touch: bid at the best bid, ask at the best ask.
- B1 joins the touch and skews both quotes one tick against each order size of inventory.
- B2, B2b and B3 are B1 plus the same overlay, driven by three different signals: B2 by
  order-flow imbalance at the best quotes, B2b by signed decay-weighted trade counts, and
  B3 by a bivariate Hawkes intensity with one fitted decay.

Each signal gives a direction u in [-1, 1] (buyers minus sellers, scaled) and a magnitude
m in [0, 1]. The overlay marks a side toxic when u passes a threshold: the ask when buyers
are arriving, since a resting ask is what gets filled just before the price rises, and the
bid in the mirror case. The toxic side steps back K ticks or is not quoted at all. The
threshold for pull rate p is the (1 - p) quantile of |u| over the training days, so the
toxic side is marked on a share p of training-day steps. Choices on the validation days,
by the highest mean daily BEF: B2 with {{pre_sel_b2}}, B2b with {{pre_sel_b2b}}, B3 at
{{pre_sel_b3}}; all three pull the toxic side and leave the magnitude rule off.

The Hawkes fit pools the training days, each an independent realisation: baselines
{{pre_hawkes_mu_b}} and {{pre_hawkes_mu_s}} per second for buys and sells, self-excitation
{{pre_hawkes_alpha_bb}} and {{pre_hawkes_alpha_ss}}, cross-excitation
{{pre_hawkes_alpha_bs}} and {{pre_hawkes_alpha_sb}}, decay {{pre_hawkes_beta}} per second
(a memory of about {{pre_hawkes_memory_ms}} ms), branching ratio {{pre_hawkes_br}}. Limitation: a constant
baseline ignores the daily cycle of activity, which tends to inflate the branching ratio.

Analysis. The confirmatory test, H1, is B3 against B2b in the primary cell: the mean over
test days of the daily difference in BEF, with a paired day-level bootstrap (10,000
resamples, seed 1729) and a paired t interval beside it. H1 holds only if both intervals
exclude 0 and the point estimate has the same sign in all 8 queue and latency cells. If the
two intervals disagree about 0, the result is inconclusive. B3 against B2, B3 against B1
and B2b against B1 are exploratory.

The minimum detectable effect was fixed before the test: s, the larger of the standard
deviations of the daily difference on training days ({{pre_s_train}} bp) and validation
days ({{pre_s_val}} bp), is {{pre_s}} bp, so with {{pre_n_test}} days at 5% two-sided and 80% power
the MDE is {{pre_mde}} bp. An effect smaller than that is one this study could not detect,
not one shown to be absent.

Canaries check the harness, not the signal. C2 gives B1 the future: it pulls the side
the mid will move against over the next 5 s; if it cannot beat B1 by 3 times the MDE, the
harness cannot turn information into PnL and the study stops. C1 runs B3 on market orders
whose buy and sell labels are shuffled within the day, so it pulls on signs that carry no
information; it is judged against R1, B1 that pulls a side at random at C1's own pull rate
(3 seeds). C3 runs B3 at zero latency as an upper bound. C4 runs B3 with the decay 10
times faster and 10 times slower.

## How the design changed before the test

The first design, v1, used the GLFT quoting model as B1 and turned the signal into a shift
of the GLFT quote centre. On the validation days it failed its oracle canary: C2, given the
future, gained {{pre_v1_c2_b1_mean}} bp a day over B1 (bootstrap {{pre_v1_c2_b1_ci}}), so
that harness could not show that information becomes PnL. A diagnosis on training and
validation days found no sign error and no latency or queue artefact. It found that GLFT,
which works in ticks, quoted about {{pre_v1_ticks_train}} ticks from the mid on training
days and {{pre_v1_ticks_val}} on validation days, as the price rose, and so traded
{{pre_v1_fills_train}} and {{pre_v1_fills_val}} times a day; and that the centre shift put
the oracle at the touch, where fills lose most, for a large share of the time
(docs/M4_diagnosis.md).

On 2026-10-25, after seeing those diagnostics and before any test-day download, I replaced
the design with v2: quote at the touch and turn the signal into stepping back on the side
it marks as toxic. The question, data, signals, metrics, hypotheses and analysis did not
change. Choosing a design after seeing validation results is a freedom I took; it is
written into the pre-registration, and the test days stayed unseen.

One rule changed after it failed. As first written for v2, C1 passed if its interval
against B1 included 0. On the validation days C1 minus B1 was {{pre_val_c1_b1_mean}} bp a
day (bootstrap {{pre_val_c1_b1_ci}}, {{pre_val_c1_b1_pos}} days above 0) and failed. An
audit found no leak, and a reason: a pulled quote rejoins at the back of the queue, so
pulling costs something even when it carries no information, and B1 never pulls. On
2026-10-26 the rule became C1 against R1. Both results are reported.

## What the signals know, before any quoting

Exploratory, on training days and checked on validation days, with no strategy, fill or
fee: the correlation, per day, between each signal's direction u and the mid change over
the next second, averaged over days.

- Every signal carries direction information on every training day. Imbalance at the best
  quotes over 1 s predicts best ({{pre_sig_train_ofi1_u1}} on training days,
  {{pre_sig_val_ofi1_u1}} on validation days), then the fitted Hawkes
  ({{pre_sig_train_hawkes_u1}}, {{pre_sig_val_hawkes_u1}}) and the 1 s trade count
  ({{pre_sig_train_ewma1_u1}}, {{pre_sig_val_ewma1_u1}}).
- Hawkes against the count it is tested against, before quoting, is mixed. Against the 1 s
  count it is ahead at the 1 s horizon ({{pre_sig_train_h_e1_1}}, bootstrap
  {{pre_sig_train_h_e1_1_ci}}, {{pre_sig_train_h_e1_1_pos}} days) and behind at 5 s
  ({{pre_sig_train_h_e1_5}}, {{pre_sig_train_h_e1_5_ci}}). Against the 5 s count, the one
  B2b uses, it is ahead at 1 s ({{pre_sig_train_h_e5_1}}, {{pre_sig_train_h_e5_1_ci}}) and
  level at 5 s ({{pre_sig_train_h_e5_5}}, {{pre_sig_train_h_e5_5_ci}}). The validation
  days give the same signs, though there the 1 s lead over the 1 s count cannot be told
  from 0 ({{pre_sig_val_h_e1_1}}, {{pre_sig_val_h_e1_1_ci}}).
- The fitted decay is not the most informative: the Hawkes with a 10 times slower decay
  does better on direction ({{pre_sig_train_slow_u1}} against {{pre_sig_train_hawkes_u1}}
  at 1 s on training days).

Limitation: a correlation of this size with the next mid change is information, not
profit. Whether it pays depends on what a fill at the touch costs, which is the next
section.

## Why quoting at the touch loses before fees

Exploratory, training days. B1 trades about {{pre_b1_fills}} times a day in the primary
cell, and its fills mark out at {{pre_b1_mk1}} bp after 1 s and {{pre_b1_mk60}} bp after
60 s, measured from the fill price: the mid moves against a fill by more than the half
spread it earns. Its mean daily
BEF is {{pre_b1_bef}} bp. Across all 8 queue and latency cells B0 and B1 range from
{{pre_base_bef_lo}} to {{pre_base_bef_hi}} bp on {{pre_base_fills_lo}} to
{{pre_base_fills_hi}} fills a day. So any overlay starts from a base that loses close to a
basis point per unit of notional before fees, and the question is only whether a signal
recovers part of it.

Limitation: the queue models estimate where our order sits; with L2 data the true position
is unknown, and fills at the touch are where that matters most.

## Tuning and canaries on the validation days

Exploratory in the sense that these days chose the settings; they are not the test. The
oracle C2 beat B1 by {{pre_val_c2_b1_mean}} bp a day (bootstrap {{pre_val_c2_b1_ci}},
{{pre_val_c2_b1_pos}} days above 0), far above 3 times the MDE ({{pre_3mde}} bp), so the
v2 harness does turn information into PnL; C2's own mean BEF, {{pre_val_c2_bef}} bp, is
still below the standard fee. C1 against R1 was {{pre_rp_c1_r1_mean}} bp (bootstrap
{{pre_rp_c1_r1_ci}}, {{pre_rp_c1_r1_pos}} days above 0), so shuffled signs did no better
than random pulls at the same rate; R1 minus B1 was itself {{pre_rp_r1_b1_mean}} bp a day
({{pre_rp_r1_b1_ci}}), about the same as C1 minus B1.

The selected overlays moved the mean daily BEF very little against B1: B3 by
{{pre_val_b3_b1_mean}} bp (bootstrap {{pre_val_b3_b1_ci}}) and B2b by
{{pre_val_b2b_b1_mean}} bp ({{pre_val_b2b_b1_ci}}). H1's statistic on these days, B3 minus
B2b, was {{pre_val_b3_b2b_mean}} bp ({{pre_val_b3_b2b_ci}}), against an MDE of
{{pre_mde}} bp. The slower wrong decay, C4 at beta divided by 10, beat B3 by
{{pre_val_c4_x01_b3_mean}} bp ({{pre_val_c4_x01_b3_ci}}). Limitation: these are 6 days
that also chose the settings, so they favour the settings chosen.

Two further comparisons were added on 2026-10-26 as exploratory. Against B1 with random
pulls at its own rate, B3 gained {{pre_rp_b3_r_b3_mean}} bp ({{pre_rp_b3_r_b3_ci}}) and
B2b {{pre_rp_b2b_r_b2b_mean}} bp ({{pre_rp_b2b_r_b2b_ci}}). Limitation, which weakens both:
random pulls start a new pulled run far more often than a signal does ({{pre_rp_runs_r_b3}}
against {{pre_rp_runs_b3}} runs an hour for B3, {{pre_rp_runs_r_b2b}} against
{{pre_rp_runs_b2b}} for B2b), and each new run gives up the queue place once, so these
differences overstate what the signal chooses, most for B2b. And B3 against B2b at the same
pull rate: {{pre_mp_5_mean}} bp at 5% ({{pre_mp_5_ci}}), {{pre_mp_10_mean}} at 10%,
{{pre_mp_25_mean}} at 25% and {{pre_mp_50_mean}} at 50%. Limitation: B3 marks in shorter
runs and so cancels more often at the same p, so part of that deficit may be the cost of
re-queuing rather than worse information.

## GLFT, the quoting model that was dropped

Exploratory, from the v1 runs. GLFT trades fills for less adverse selection per fill. On
training days, raising risk aversion gamma from 0.025 to 0.4 cut the median day from
{{pre_glft_fills_low_gamma}} to {{pre_glft_fills_gamma04}} fills and raised the best mean
daily BEF from {{pre_glft_bef_low_gamma}} to {{pre_glft_bef_gamma04}} bp. At the chosen
setting its mean daily BEF was {{pre_glft_chosen_bef}} bp on about {{pre_glft_chosen_fills}}
fills a day: a smaller loss per unit of notional than the touch base, on about
{{pre_glft_fill_ratio}} times fewer fills. Because the model works in ticks, its distance from the mid grew with the
price: across the 18 days the correlation of the mid with that distance is
{{pre_glft_corr}}. That is why it barely traded on the validation days, and why v1's oracle
had little to work with.

Limitation: the mean of daily BEF weights a day with a few fills like a day with hundreds,
so the GLFT means on few fills are noisy.

## Results on the test days

Primary cell (risk-averse queue, high latency), {{n_test_days}} test days. The mean daily
difference in break-even fee, B3 minus B2b, is {{h1_mean_bp}} bp, with a bootstrap
interval from {{h1_ci_low_bp}} to {{h1_ci_high_bp}} bp and a paired t interval from
{{h1_t_low_bp}} to {{h1_t_high_bp}} bp. B3 was ahead on {{h1_days_positive}} of
{{h1_n_days}} days, and the point estimate has the sign of the primary cell in
{{h1_cells_same_sign}} of 8 cells. The MDE for this number of days is {{mde_bp}} bp, with
s = {{s_bp}} bp. The median ratio of B3 to B2b traded notional is {{selectivity_ratio}}.

{{h1_statement}}

The statement above is chosen by script from these sentences, committed before the test:

| Outcome on test days | Statement |
|---|---|
| H1 holds, D > 0 | The fitted Hawkes overlay added X bp of edge per unit of notional over a decay-weighted trade count, with interval [L, U], in every queue and latency cell. |
| Intervals include 0 and abs(mean D) < MDE | No detectable difference between the Hawkes overlay and a decay-weighted trade count. The study could detect effects of MDE bp or larger. |
| Intervals include 0 and abs(mean D) >= MDE | Inconclusive: the point estimate is large but the test set is too small to separate it from noise. |
| Primary intervals exclude 0 but the sign flips in some cell | Does not hold. The result depends on the queue or latency model. |
| H1 holds, D < 0 | The Hawkes overlay did worse than a decay-weighted trade count by X bp, interval [L, U]. |
| C1 fails on test days | The signal's gain does not depend on event signs, so it is not order-flow information. Primary result reported but not interpreted. |

Exploratory, same statistic: B3 minus B2 {{h2_mean_bp}} bp ({{h2_ci_low_bp}} to
{{h2_ci_high_bp}}), B3 minus B1 {{h3_mean_bp}} bp ({{h3_ci_low_bp}} to {{h3_ci_high_bp}}),
B2b minus B1 {{h4_mean_bp}} bp ({{h4_ci_low_bp}} to {{h4_ci_high_bp}}). Against random
pulls at their own rates: B3 {{rp_b3_mean_bp}} bp ({{rp_b3_ci_low_bp}} to
{{rp_b3_ci_high_bp}}), B2b {{rp_b2b_mean_bp}} bp ({{rp_b2b_ci_low_bp}} to
{{rp_b2b_ci_high_bp}}), with the run-length limitation stated above.

![Fig. 1. B3 minus B2b in break-even fee on each test day in the primary cell, with the
mean and both intervals. Simulated fills on historical data.](fig_daily_d.svg)

![Fig. 2. Mean of B3 minus B2b in each of the 8 queue and latency cells; H1 needs one sign
in all of them. Simulated fills on historical data.](fig_cells.svg)

Limitations, stated with the result: simulation only, no real fills; queue position is
estimated, not observed; an order at the front of the queue fills in full on any trade at
its price; funding payments are not modelled.

## Canaries on the test days

C1 against R1: {{c1_r1_mean_bp}} bp ({{c1_r1_ci_low_bp}} to {{c1_r1_ci_high_bp}}); C1
against B1, the rule first written: {{c1_b1_mean_bp}} bp ({{c1_b1_ci_low_bp}} to
{{c1_b1_ci_high_bp}}). C2 against B1: {{c2_b1_mean_bp}} bp.

{{canary_statement}}

## What I would do with L3 data and real fills

L3 data lists every order in the queue, so the queue position this study estimates with
four models would be known. That removes the largest model risk in every fill at the touch,
and it would show whether the cost of pulling a quote, which drove the C1 result, is as
large as the risk-averse model makes it. I would rerun the same pre-registered comparison
with the true queue and keep the four models as a check on how wrong each one was.

Real fills would show what a replay cannot: how other participants react to our quotes,
how often a post-only order is rejected, and what latency really is from a given location.
I would start with the smallest size the venue allows on a few days, log every order and
fill, and compare each fill with its simulated twin on the same day. Only the gap between
the two would tell how far the simulated numbers here can be trusted.

## How it is tested

- Signals are causal: a test replaces every event after time t with random events and
  checks that each signal is unchanged up to t.
- The online signals equal their offline versions to 1e-9.
- The Hawkes fit recovers known parameters from simulated data.
- Accounting reconciles: cash plus inventory at the mark equals gross PnL to 1e-6 USDT on
  every run, and fees applied afterwards equal hftbacktest's own fee model on one day.
- Only the oracle canary may look ahead, and no strategy or signal file can import the
  code that computes markouts.
- The test-day loader refuses a test date until the tag is public.
- Every number on this page is filled by script from results/summary.json (test days) or
  paper/pre_test.json (training and validation days); a check fails the build if a result
  section holds a number typed by hand.

## Reproduce

    make data DAYS=train
    make data DAYS=val
    make data DAYS=test      # refused until the tag prereg-v1 is public
    make run CFG=configs/runs/<name>.yaml
    make paper

Code: src/toxic_flow (engine, strategies, signals, eval), the plan in PREREGISTRATION.md,
the history of choices in docs/, and every run's results in results/, each tied to a
committed config.
