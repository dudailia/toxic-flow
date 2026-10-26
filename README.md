# toxic-flow

A pre-registered study on Binance BTCUSDT perpetual futures. It asks whether a causal
Hawkes estimate of market-order intensity helps a passive market maker decide when to step
back from the touch, compared with a decay-weighted trade count built from the same market
orders and with order-flow imbalance. The edge is the break-even maker fee: gross PnL per
unit of traded notional.

All results are from simulation on historical data: an L2 replay in hftbacktest of
Tardis.dev files. No order was sent to an exchange. Nothing here is a claim about live
trading, real fills or profit.

- The plan, frozen by the git tag prereg-v1 before any test day was downloaded:
  PREREGISTRATION.md. Its Design history says what changed before the tag, when and why.
- Milestones and acceptance criteria: SPEC.md. What remains before the tag:
  docs/TAG_CHECKLIST.md.
- Changes after the tag: DEVIATIONS.md.
- The paper: paper/template.md, built by `make paper` once the test days have run, or by
  `make paper-draft` before that (test-day results stay as {{key}} placeholders).

## Reproduce

Every run needs a config committed to git and a clean working tree, and writes
`results/<config hash>/` with the config, the commit and the metrics. Steps marked (Ilia)
are decisions or actions only Ilia takes. Configs for the v2 design come from
scripts/make_v2_configs.py; an existing config is never overwritten.

Setup:

    uv sync
    make hooks        # the pre-commit hook runs make check
    make check        # lint, fast tests, leakage tests, writing lint

1. Training and validation data, then quality reports, market-order events and the
   exclusion rules, for each day:

       make data DAYS=train
       make data DAYS=val
       uv run python -m toxic_flow.data.validate YYYY-MM-DD
       uv run python -m toxic_flow.events.market_orders YYYY-MM-DD
       uv run python -m toxic_flow.data.exclusions

2. Signal constants and overlay thresholds from the training days (pooled Hawkes fit, K,
   theta_u and theta_m):

       uv run python scripts/fit_signals.py
       uv run python scripts/fit_thresholds.py

3. B0 and B1 on the training days in all 8 queue and latency cells (they have no
   parameters, so nothing is chosen):

       uv run python scripts/make_v2_configs.py train
       make run CFG=configs/runs/v2_train.yaml

4. Overlay tuning on the validation days, primary cell, in two halves of the days, then
   the section 4 rule:

       uv run python scripts/make_v2_configs.py tune
       make run CFG=configs/runs/v2_tune_val_a.yaml
       make run CFG=configs/runs/v2_tune_val_b.yaml
       uv run python scripts/m4_v2.py select --tune results/<a> results/<b>

   (Ilia) approve the choice into configs/selected.yaml.

5. Canaries, the minimum detectable effect and the random-pull controls:

       uv run python scripts/make_v2_configs.py canaries
       uv run python tests/canary/run_c2.py configs/runs/v2_canaries_val.yaml
       uv run python scripts/make_v2_configs.py mde
       make run CFG=configs/runs/v2_mde_train.yaml
       uv run python scripts/make_v2_configs.py random results/<canaries>
       make run CFG=configs/runs/v2_random_pulls_val.yaml
       uv run python scripts/m4_v2.py report --train-b results/<v2_train> \
           --tune results/<a> results/<b> --canaries results/<canaries> --mde results/<mde>
       uv run python scripts/m4_v2.py random --random results/<random> \
           --canaries results/<canaries> --tune results/<a> results/<b>

   (Ilia) tag and push prereg-v1, after docs/TAG_CHECKLIST.md is done.

6. The test run, once. The loader refuses test days until the tag exists locally and on
   the public remote. Two runs are planned: the grid, then the random-pull controls at the
   grid's realised pull rates.

       make data DAYS=test
       (quality reports, events and exclusions as in step 1)
       git add data/manifest.json docs/data_quality && git commit   (AC5.2: exclusions first)
       uv run python scripts/make_v2_configs.py confirmatory
       git add configs/runs/confirmatory.yaml && git commit
       uv run python tests/canary/run_c2.py configs/runs/confirmatory.yaml
       git add results/<confirmatory> && git commit
       uv run python scripts/make_v2_configs.py controls results/<confirmatory>
       git add configs/runs/confirmatory_controls.yaml && git commit
       make run CFG=configs/runs/confirmatory_controls.yaml
       git add results/<controls> && git commit
       uv run python scripts/analyse.py summary --s-bp <s from section 9> \
           --out results/summary.json results/<confirmatory> results/<controls>
       git add results/summary.json && git commit
       make paper
       (AC5.4) the leakage-auditor on both runs, its report in docs/audit_M5.md
       uv run python scripts/check_milestone.py M5

A run refuses a config that is not committed or a working tree with changes, so each
result maps to a commit; the commits above come after the tag, which scripts/analyse.py
checks. C2, the oracle canary, is the only strategy allowed to look ahead, so configs that include
it run through tests/canary/run_c2.py rather than make run. `make check-full` adds the
slow tests; three of them need 2024-01-01 converted on disk.

## Layout

- src/toxic_flow/data: download (with the test-day lock), conversion, quality checks.
- src/toxic_flow/events: market orders, collapsed from trades.
- src/toxic_flow/signals: OFI, decay-weighted counts, the Hawkes fit and online intensity.
- src/toxic_flow/strategies: the quoting loops (numba, run inside hftbacktest).
- src/toxic_flow/engine: run configs, the queue and latency grid, one run per config.
- src/toxic_flow/eval: metrics, markouts and the pre-registered analysis. Anything that
  looks ahead lives here or in tests/canary/, never in strategies or signals.
- docs/: the record of every choice before the tag, including the v1 design that failed.
- results/: one directory per run, named by the config hash.
