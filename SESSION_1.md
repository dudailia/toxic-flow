# Session 1: M0, recon and guards

## Before the session (Ilia, by hand, about 20 minutes)

1. Create a public GitHub repo `toxic-flow` with no template. Clone it.
2. Copy this kit into it. Commit "kit: spec, prereg draft, Claude Code config" and push.
   The public history is part of the evidence, so push from day one.
3. Install uv. Check `python3 --version` is 3.11 or newer; the hooks run on it.
4. Start Claude Code in the repo and accept the workspace trust dialog. Hooks and the
   allow rules in .claude/settings.json do nothing until you do.
5. Run `/hooks` and confirm three hooks: PreToolUse guard, PostToolUse ruff, Stop check.
6. Test the guard once: ask Claude to "create the file data/raw/test.txt". It must be
   denied. Then ask it to edit configs/splits.yaml; you must get a prompt. Say no.
7. Auto mode is fine for this session. The deny rules and hooks still apply in it.

## Prompt to paste (start in plan mode)

```
We are implementing milestone M0 of SPEC.md and nothing past it.

Read CLAUDE.md, the M0 section of SPEC.md, and sections 2 and 3 of PREREGISTRATION.md.
scripts/check_milestone.py already contains the M0 checks. Read it so you know exactly
what has to pass. Do not edit it, and do not edit configs/splits.yaml.

Make a plan covering, in this order:
1. uv project on Python 3.12. Pin hftbacktest to the newest release that is at least
   two weeks old, and say which version and why. Other deps: polars, pyarrow, numpy,
   scipy, numba, pyyaml, pytest, ruff.
2. Makefile targets: check (ruff, then pytest on tests/ excluding tests marked slow),
   check-full, hooks (installs .git/hooks/pre-commit running make check), data, plus
   stubs for run and paper.
3. tests/test_writing.py: fail on any word in tests/writing_rules.txt (whole word, case
   insensitive) or any em dash, in every .md file and anything under paper/, excluding
   CLAUDE.md, .claude/ and tests/writing_rules.txt.
4. src/toxic_flow/data/split_lock.py and tests/leakage/test_split_lock.py, before any
   download code. The lock refuses a test date unless prereg-v1 is listed by
   `git tag --list` and by `git ls-remote --tags origin`. Tests run in a temporary git
   repo and cover: no tag, local tag only, tag on both. Expect an approval prompt from me
   for these protected paths.
5. scripts/recon.py: GET https://api.tardis.dev/v1/exchanges/binance-futures and record
   what it says about BTCUSDT. Then HEAD each of the 68 URLs of the form
   https://datasets.tardis.dev/v1/binance-futures/<type>/<yyyy>/<mm>/<dd>/BTCUSDT.csv.gz
   and write data/recon.json in the shape check_milestone.py expects. HEAD only; never GET
   a test-day file. Summarise sizes per split in docs/DATA_RECON.md.
6. configs/venue.yaml with by_date entries: tick_size, lot_size, min_notional,
   maker_fee_bps, taker_fee_bps (standard tier, USDT-M), source (URL). Use Binance's own
   announcements and fee pages. If you cannot find a dated source for a value, write TBD
   and a one-line question for me. Do not estimate.
7. docs/ENGINE.md for the pinned hftbacktest version: exact names for Tardis conversion,
   the risk-averse model, the power-function model with n = 3 and n = 2, the log model,
   the latency models (including how to build order latency from feed latency), the
   exchange models, the fee model. Link the pinned version's docs or source for each.
8. download.py and convert.py, then `make data DAYS=2024-01-01`, and nothing else.
   Record url, bytes, sha256, downloaded_at, split in data/manifest.json.
9. A minimal fixed-spread loop (1 tick each side, minimum order size, risk-averse queue,
   order latency from feed latency) on 2024-01-01. Record wall time and fill count.
   It becomes B0 in M2, so keep it small and readable.
10. docs/DATA_RECON.md sections "## Benchmark" (raw and converted bytes, conversion time,
    loop wall time, fill count, CPU model, cores, RAM) and "## Compute projection"
    (run counts for M4 tuning and the M5 grid from SPEC.md, times measured wall time,
    divided by usable cores).

Mark every fact you could not verify as [TBD: question]. Show me the plan and wait.
```

## After approving the plan

```
/goal `uv run python scripts/check_milestone.py M0` exits 0 and `make check` exits 0,
both shown in the transcript, and no file for any test date exists under data/. Stop
early and list the open questions if a venue value cannot be sourced. Stop after 40 turns.
```

## When the goal clears

1. `/code-review`, then "use the leakage-auditor agent on the M0 changes".
2. `/viva M0`. Answer viva/M0.md yourself, no AI. Then `/viva M0 grade`.
3. Paste into Claude chat: the check_milestone output, docs/DATA_RECON.md, the list of
   TBD questions, and the auditor's report. Chat reviews before you start M1.
4. `/clear` before M1.
