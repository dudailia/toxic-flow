# toxic-flow: pre-registered market-making study

Research repo. Correctness and honesty beat speed and polish. Ilia must defend every line
in a 45-minute technical interview, so write the simplest correct code and comment the
reason behind non-obvious choices, not the mechanics.

## Commands
- make check: ruff, fast tests, leakage tests, writing lint. Under 2 minutes. Must pass
  before any commit; the pre-commit hook enforces it.
- make check-full: adds slow tests (Hawkes parameter recovery, engine smoke runs).
- make data DAYS=train|val|test|YYYY-MM-DD: download, hash, convert. Test days refuse
  until tag prereg-v1 exists locally and on the public remote.
- make run CFG=configs/runs/<name>.yaml: one grid run, writes results/<config_hash>/.
- make paper: rebuild every figure and number from results/ only.
- uv run python scripts/check_milestone.py M<n>: acceptance criteria for a milestone.

## Hard rules
- Never create, move or delete git tags. Ilia creates and pushes prereg-v1 himself.
- Never load test-day data before prereg-v1. The loader enforces this. Do not work around
  it and do not add flags, env vars or fixtures that bypass it outside tests/leakage/.
- PREREGISTRATION.md is frozen after prereg-v1. Changes go in DEVIATIONS.md with date,
  reason and effect on results. Both the original and the changed result get reported.
- Every number in the paper comes from a results/ file produced by a committed config.
- Code in src/toxic_flow/strategies and src/toxic_flow/signals must not import from
  src/toxic_flow/eval. Markouts and anything forward-looking live only in eval.
- Signals are causal: the value used at decision time t depends only on events the
  strategy has received by t (local timestamp, after feed latency). Each signal has a
  future-perturbation test in tests/leakage/.
- Fitted parameters and normalisation constants come from training days only. Overlay
  tuning uses validation days only. Intraday normalisers use trailing windows only.
- Report every result across the full queue-model grid and both latency settings.
  A result that holds only under the optimistic queue models is reported as not holding.
- Use hftbacktest for simulation. No custom matching engine. If hftbacktest cannot do
  something, stop and ask Ilia.
- Polars and Parquet for tabular data. data/raw is immutable, pinned by SHA-256 in
  data/manifest.json. Only the downloader writes there and it never overwrites.
- No invented numbers about the data, venue specs, fees or results. Unknowns become
  [TBD: question] and go on the list for Ilia.
- Never claim live trading, real fills, profitability or deployability.
- Edits to paths in .claude/protected-paths.txt prompt Ilia. Do not route around that.

## Workflow
- Read the milestone's section of SPEC.md first. Plan mode before each milestone; skip
  it for one-line fixes.
- Before implementing a milestone, write its checks into scripts/check_milestone.py from
  SPEC.md and get Ilia's approval. Tests are set before the code that must pass them.
- A milestone closes when its check script passes, /code-review and the leakage-auditor
  report nothing that changes a conclusion, and Ilia passes /viva. Only Ilia runs /viva
  and only Ilia marks a milestone closed in SPEC.md.
- After two failed attempts at the same problem, stop and tell Ilia what you tried.
- If a result looks too good (positive net PnL at the standard maker fee under the
  risk-averse queue model, a failed canary, any run beating its zero-latency twin),
  stop and run the leakage-auditor before anything else.
- When compacting, keep: current milestone, failing tests, open [TBD] items for Ilia.

## Writing
- Plain words. No em dashes. Banned words live in tests/writing_rules.txt and make check
  enforces them on every .md and paper file.
- State limitations next to results, not in a footnote.
