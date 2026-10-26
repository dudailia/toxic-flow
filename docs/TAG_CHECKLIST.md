# Before the tag prereg-v1

What must happen before Ilia creates and pushes the annotated tag prereg-v1 (CLAUDE.md:
only Ilia touches tags). State as of 2026-10-26, commit given in the git log of this file.
Each item says who acts and where the material is. The order is the order to do them in.

## 1. Protected-path changes waiting for Ilia's approval

Nothing below has been applied: each target is on .claude/protected-paths.txt.

1. Q14, the stricter test-day lock, first. docs/proposals/Q14/split_lock.py replaces
   src/toxic_flow/data/split_lock.py and docs/proposals/Q14/test_split_lock.py replaces
   tests/leakage/test_split_lock.py. The lock then opens a test day only if prereg-v1 is an
   annotated tag, origin is the URL in configs/repo.yaml (committed), and the remote tag
   hash equals the local one. Approved in substance on 2026-10-22 but not applied, because
   that block allowed no protected edit. It goes first because the lock is the only thing
   that keeps test days closed until the tag, and the tag must be made against the final
   lock. Test record: docs/proposals/Q14/RESULTS.md.
2. tests/pending_leakage/ into tests/leakage/ (all three run in make check today, from the
   pending folder):
   - test_layering.py: no import path from strategies or signals into eval (AC2.6).
   - test_future_perturbation.py: replacing events after t leaves each signal unchanged up
     to t (AC3.1).
   - test_forward_arrays.py: no strategy or signal file names a forward-looking array; only
     tests/canary/ builds one (AC3.6).
3. scripts/check_milestone.py has checks for M0 only. Proposals to paste in:
   - docs/proposals/check_M1_M3.md: M1 and M3.
   - docs/proposals/check_M2.md: M2. Under v2, AC2.5 (B0 h and B1 gamma and window chosen
     on training days) no longer applies, because v2 B0 and B1 have no parameters; SPEC.md
     M2 needs Ilia's wording for it before the check can pass. AC2.4 (risk-averse has no
     more fills than any other queue model) can be read from the v2 B0 and B1 run
     results/4db60c584c71.
   - docs/proposals/check_M4_v2.md: M4 under v2 (new). It replaces the M4 part of
     docs/proposals/check_M4_M5.md, which reads the v1 runs and judges C1 against B1.
   - docs/proposals/check_M4_M5.md: keep its M5 part for after the tag.
4. docs/proposals/check_M1_M3.md and check_M2.md were corrected on 2026-10-26 after a dry
   run (section 2): three M1 and M3 checks read paths or headings that the outputs no
   longer have, and AC2.3 passed when its test was skipped. Each file says what changed.

## 2. Milestone checks and vivas

Dry run on 2026-10-26: each proposal's code executed in the namespace of the current
scripts/check_milestone.py, which was not changed. PASS means the check would pass once
pasted in.

| Milestone | Check in check_milestone.py | Dry run of the proposal | What fails, and who fixes it |
|---|---|---|---|
| M0 | yes | 21 of 21 (the script itself, 2026-10-26) | nothing |
| M1 | no (check_M1_M3.md) | 12 of 12 | nothing |
| M2 | no (check_M2.md) | 8 of 11 | AC2.5: v2 B0 and B1 have no parameters, so SPEC.md M2 needs Ilia's v2 wording and the check a v2 form. AC2.6: test_layering.py is still in tests/pending_leakage/. AC2.3: the fee-equivalence test was skipped because 2024-01-01 is not converted (the dry run before the correction counted the skip as a pass); converting that day and running `make check-full` makes it run. |
| M3 | no (check_M1_M3.md) | 10 of 11 | AC3.1: test_future_perturbation.py is still in tests/pending_leakage/. |
| M4 | no (check_M4_v2.md) | 4 of 4 | AC4.1 to AC4.4 pass: selection reproduced from the tuning runs, C2 - B1 2.102 bp against 3 x MDE 0.069 bp, C1 - R1 interval [-0.0023, 0.0038], no [TBD] and the writing lint passes. AC4.5 is the viva. |

Vivas: none is recorded. SPEC.md lists M0 to M6 as open, and there is no viva/ directory.
SPEC.md requires /viva M0 to M4, run by Ilia only, before the milestones close; AC4.5
needs /viva M4 before the tag.

Also before the tag, by the milestone rule in CLAUDE.md: /code-review and the
leakage-auditor on the M4 v2 work. The auditor ran on the v2 canaries (no leak, findings
in docs/M4_v2_draft.md). The random-pull code and run (engine.run.random_pulls,
results/c274b2def28e) have had neither, since no canary failed and no result looked too
good after it.

## 3. Disk for the 16 test days

Free now: 14 GB (`df -H /`, 2026-10-26, decimal GB). The floor Ilia set is 3 GB (the
watchdog stops runs below it). Raw files may never be deleted, so all 16 test days' raw
files must fit at once.

| Item | GB | Basis |
|---|---|---|
| Raw, 16 test days | about 9.9 (4.2 to 16.2) | estimate in docs/disk_budget.md: the 18 measured train and val days' mean, smallest and largest day, times 16; test-day sizes cannot be known before the tag |
| Converted cache, one day at a time | at most about 1.4 | docs/disk_budget.md, largest day at the measured ratio |
| Results of the confirmatory run | about 1.8 | estimate: about 54 cells a day (B0 to B3 in 8 cells, the canaries and the 9 random-pull runs) times 16 days, at the 2.1 MB a cell of results/4db60c584c71 |
| Floor | 3.0 | Ilia's rule |
| Total | about 16.1 (10.4 to 22.4) | |

At the mean estimate the test days need about 2 GB more than is free, and up to about 8 GB
more if they are as large as the largest training day. Swap lives on the same disk and has
taken up to 1.7 GB in one conversion before (docs/disk_budget.md), so the margin should be
larger than the table. Options for Ilia: free space outside the repo; or delete the
per-fill files results/*/fills_*.parquet (3.8 GB, gitignored; every
number in the docs comes from metrics.parquet, and each can be rebuilt by rerunning its
committed config); or an external disk for data/raw. None of these was done.

## 4. Other items before the tag

- PREREGISTRATION.md: no [TBD] left (tests/unit/test_prereg.py). Ilia should read the
  text filled on 2026-10-26, since three items were his open decisions and are now
  written as the code runs them: the exchange model (Q3, no partial fills), the queue
  model API names (Q2) and the third fee level (Q6, the Liquidity Provider Program Tier 1
  rate of -0.1 bp, hypothetical before 2025-03-03). The text came from
  docs/proposals/prereg_m0_tbds.md.
- docs/proposals/section10_canaries.md: Q24 (one permutation for C1; now C1 has one seed
  and its control R1 three), Q26 (C3 removes order latency only, not feed latency), Q29
  (the C3 flag compares means) and Q30 (order latency interpolated from one-second feed
  latency samples, stated in section 3) are written into PREREGISTRATION.md as the code
  does them. Ilia confirms or changes each before the tag.
- The C1 rule revision of 2026-10-26 is disclosed in the Design history; it was made
  after seeing C1 fail against B1 on the validation days.
- M5 code for v2 does not exist yet. engine/configs.confirmatory builds the v1 grid. The
  v2 confirmatory run needs B0 to B3 v2 in all 8 cells, the canaries in the primary cell,
  C3 at zero latency, and R1, R_B3 and R_B2b after the runs whose realised rates they
  take (a second config built from the first run's metrics, as
  scripts/make_v2_configs.py random does now). Writing and reviewing it before the tag
  would freeze the test-day code with the plan; after the tag it is allowed but should be
  done before any test-day download.
- Open questions in docs/SESSION_REPORT.md that are still Ilia's: Q32 to Q51 (earlier
  blocks), and the older Q2, Q3, Q6, Q24, Q26, Q29 and Q30 named above. Q52 to Q54 are
  decided (2026-10-26).
- After the tag, by Ilia: push it, then write the first entry of DEVIATIONS.md (tag,
  commit hash, push time on GitHub).
