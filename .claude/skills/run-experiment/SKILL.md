---
name: run-experiment
description: Run one committed backtest config across the queue-model and latency grid.
disable-model-invocation: true
argument-hint: "configs/runs/<name>.yaml"
---
Config: $ARGUMENTS

1. Refuse if `git status --porcelain` shows any change. Results must map to a commit.
2. Refuse if the config file is not tracked by git (`git ls-files --error-unmatch`).
3. Refuse if the config covers any test date and `git tag --list prereg-v1` is empty.
   The loader also refuses; this check just fails earlier.
4. Run `make run CFG=$ARGUMENTS`.
5. Show the summary table: per strategy and cell, mean break-even fee, mean net PnL at
   the standard maker fee, fills per hour, mean 10 s markout. Then the canary results.
6. Flag, in bold, anything that looks too good: positive mean net PnL at the standard
   maker fee in the risk-averse queue cell, any run beating its zero-latency twin, any
   canary outside its pass criterion. If anything is flagged, run the leakage-auditor
   agent on this results directory before saying anything else about the result.
