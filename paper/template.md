# Does a Hawkes estimate of order flow help a passive market maker?

A pre-registered study on Binance BTCUSDT perpetual futures, in L2 replay simulation only.
Every number in this page is filled from results/summary.json; none is typed by hand.

## Question

On {{n_test_days}} test days, does a causal Hawkes estimate of market-order intensity raise
the break-even maker fee of a GLFT market maker, compared with a decay-weighted trade count
built from the same events? The hypotheses, analysis and stopping rules were frozen at the
tag prereg-v1, created on {{prereg_tagged_at}}.

## Data and simulation

Tardis.dev incremental book and trade files for {{n_train_days}} training, {{n_val_days}}
validation and {{n_test_days}} test days. Simulation in hftbacktest {{hftbacktest_version}},
across four queue models and two latency settings. Orders are the minimum size the venue
allows, so the replay assumption that our orders do not move the market stays close to true.

## Results

Primary cell (risk-averse queue model, high latency): the mean daily difference in
break-even fee between the Hawkes overlay and the decay-weighted count is {{h1_mean_bp}} bp,
with a bootstrap interval from {{h1_ci_low_bp}} to {{h1_ci_high_bp}} bp and a paired t
interval from {{h1_t_low_bp}} to {{h1_t_high_bp}} bp. The study could detect effects of
{{mde_bp}} bp or larger. {{h1_statement}}

![Difference in break-even fee, B3 minus B2b, on each test day in the primary cell, with
its mean and both intervals](fig_daily_d.svg)

![Mean difference in each of the 8 queue and latency cells; H1 needs one sign in all of
them](fig_cells.svg)

Limitations, stated with the result: simulation only, no real fills; queue position is
estimated, not observed; funding payments are not modelled.

## Canaries

{{canary_statement}}

## What I would do with L3 data and real fills

L3 data would replace the estimated queue position with the true one, which removes the
main source of model risk in every fill. Real fills would show what the replay cannot: how
the market reacts to our own orders.

## Reproduce

    make data DAYS=train
    make data DAYS=val
    make data DAYS=test
    make run CFG=configs/runs/<name>.yaml
    make paper
