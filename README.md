# toxic-flow

A pre-registered study of whether a Hawkes estimate of market-order intensity helps a
passive market maker on BTCUSDT perpetual futures, compared with cheaper order-flow
signals, in an L2 replay backtest. Results are from simulation on historical data only.

Status and plan: SPEC.md. Hypotheses and analysis, frozen at tag prereg-v1: PREREGISTRATION.md.

## Reproduce

Every run needs a config committed to git and a clean working tree, and writes
`results/<config hash>/`. Steps marked (Ilia) are decisions or actions only Ilia takes.

Setup:

    uv sync
    make hooks        # pre-commit runs make check
    make check

1. Training and validation data, then quality reports, market-order events and the
   exclusion rules, for each day:

       make data DAYS=train
       make data DAYS=val
       uv run python -m toxic_flow.data.validate YYYY-MM-DD
       uv run python -m toxic_flow.events.market_orders YYYY-MM-DD
       uv run python -m toxic_flow.data.exclusions

2. B0 and B1 on the training days, all 8 cells. The B1 grid is Ilia's choice.

       uv run python scripts/make_configs.py training --gammas G1,G2 --windows W1,W2
       make run CFG=configs/runs/train_b0_b1.yaml
       uv run python scripts/select_params.py results/<hash> B0 docs/selection/B0_train.md
       uv run python scripts/select_params.py results/<hash> B1 docs/selection/B1_train.md

   (Ilia) write B0 and B1 into configs/selected.yaml from those tables.

3. Signal constants from the training days (pooled Hawkes fit, K):

       uv run python scripts/fit_signals.py

4. Overlay tuning on the validation days, primary cell:

       uv run python scripts/make_configs.py tuning
       make run CFG=configs/runs/tune_val.yaml
       uv run python scripts/select_params.py results/<hash> B2 docs/selection/B2_val.md

   and the same for B2b and B3. (Ilia) add B2, B2b and B3 to configs/selected.yaml.

5. Canaries and the minimum detectable effect:

       uv run python scripts/make_configs.py canaries
       uv run python scripts/make_configs.py mde_train
       uv run python tests/canary/run_c2.py configs/runs/canaries_val.yaml
       make run CFG=configs/runs/mde_train.yaml
       uv run python scripts/analyse.py mde --train results/<hash> --val results/<hash>

   Fill every [TBD] in PREREGISTRATION.md. (Ilia) tag and push prereg-v1.

6. The test run, once. The loader refuses test days until the tag exists locally and on
   the public remote.

       make data DAYS=test
       (quality reports and exclusions as in step 1)
       uv run python scripts/make_configs.py confirmatory
       uv run python tests/canary/run_c2.py configs/runs/confirmatory.yaml
       uv run python scripts/analyse.py summary --s-bp <s from section 9> \
           --out results/summary.json results/<hash>
       make paper

C2, the oracle canary, is the only strategy allowed to look ahead, so configs that
include it run through tests/canary/run_c2.py rather than make run.
