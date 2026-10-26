# Before the tag prereg-v1

What must happen before Ilia creates and pushes the annotated tag prereg-v1 (CLAUDE.md:
only Ilia touches tags). State as of 2026-10-26, commit given in the git log of this file.
Each item says who acts and where the material is. The order is the order to do them in.

## 1. Protected-path changes

All applied on 2026-10-26, each through Ilia's permission prompt while he was at the
keyboard:

1. Q14, the stricter test-day lock (commit 3d98a41). src/toxic_flow/data/split_lock.py
   opens a test day only if prereg-v1 is an annotated tag, origin is the URL in
   configs/repo.yaml, and the remote tag hash equals the local one; four new tests in
   tests/leakage/test_split_lock.py (15 pass). On this checkout the lock is closed: no
   tag. Record of the test before the change: docs/proposals/Q14/RESULTS.md.
2. tests/pending_leakage/ moved into tests/leakage/ (commit 4814669): test_layering.py
   (AC2.6), test_future_perturbation.py (AC3.1), test_forward_arrays.py (AC3.6).
3. scripts/check_milestone.py has checks for M0 to M5 (commit 14e3386), pasted from
   docs/proposals/check_M1_M3.md, check_M2.md, AC2_5_v2.md, check_M4_v2.md and the M5 part
   of check_M4_M5.md. Choices made on 2026-10-26: SPEC AC2.5 has the v2 text (B0 and B1
   have no parameters); AC2.1 and AC2.4 read the v2_train run only, and AC2.4 covers B0
   as well as B1 (Ilia); the M2 viva topics add the join-the-touch loss and keep GLFT
   (Ilia). Commit 50ae502.
4. AC0.5 walks data/ through symlinks (commit 9cdea27). Path.rglob in Python 3.12 does
   not enter a symlinked folder, so after the SSD move (section 3) the check "no test-day
   path under data/" would have passed without looking at data/raw. It now uses
   os.walk(followlinks=True); found while writing docs/ssd_move.md.

## 2. Milestone checks and vivas

`uv run python scripts/check_milestone.py M<n>` on 2026-10-26, after the changes above:

| Milestone | Result | What fails |
|---|---|---|
| M0 | 21 of 21 | nothing |
| M1 | 12 of 12 | nothing |
| M2 | 11 of 11 | nothing. AC2.3 runs the slow fee test, which needs 2024-01-01 converted (0.78 GB cache kept); evicting that cache makes AC2.3 fail again, not pass on a skip |
| M3 | 11 of 11 | nothing |
| M4 | 8 of 8 | nothing. AC4.1 to AC4.4 pass: selection reproduced from the tuning runs, C2 - B1 2.102 bp against 3 x MDE 0.069 bp, C1 - R1 interval [-0.0023, 0.0038], no [TBD] and the writing lint passes |
| M5 | 4 of 8 | AC5.1 to AC5.4: no tag, no test-day run, no docs/audit_M5.md. Expected until after the tag |

Vivas: none is recorded. SPEC.md lists M0 to M6 as open, and there is no viva/ directory.
SPEC.md requires /viva M0 to M4, run by Ilia only, before the milestones close; AC4.5
needs /viva M4 before the tag. This is the main open item.

Also before the tag, by the milestone rule in CLAUDE.md: /code-review of the code added
on 2026-10-26 after the last review (from 3d98a41: the run-length control in
engine/run.py and engine/configs.py, the analysis and report changes, scripts/verify_raw.py
and the check script). The leakage-auditor ran on the run-length run (section 4,
docs/audit_run_length.md).

## 3. Disk for the 16 test days

Free now: 17 GB (`df -H /`, 2026-10-26 after this block, decimal GB; it moves with swap,
between 11 and 19 GB today). The floor Ilia set is 3 GB (the watchdog stops runs below it).
Raw files may never be deleted, so all 16 test days' raw files must fit at once.

| Item | GB | Basis |
|---|---|---|
| Raw, 16 test days | about 9.9 (4.2 to 16.2) | estimate in docs/disk_budget.md: the 18 measured train and val days' mean, smallest and largest day, times 16; test-day sizes cannot be known before the tag |
| Converted cache, one day at a time | at most about 1.4 | docs/disk_budget.md, largest day at the measured ratio |
| Results of the two test-day runs | about 2.0 | estimate: about 60 cells a day (B0 to B3 in 8 cells, the canaries, 9 R and 6 RL runs) times 16 days, at the 2.1 MB a cell of results/4db60c584c71 |
| Floor | 3.0 | Ilia's rule |
| Total | about 16.3 (10.6 to 22.6) | |

Decided by Ilia on 2026-10-26: an external SSD for data/raw. docs/ssd_move.md has the
steps (only data/raw moves, through a symlink; APFS; copy, verify the copy, switch, verify
through the link; the internal copy stays until Ilia removes it). scripts/verify_raw.py
re-checks every raw file's size, SHA-256 and read-only mode against data/manifest.json:
0 problems over the 36 files on 2026-10-26, in 13 s. .gitignore now ignores data/raw as a
link as well, which the old `data/raw/` pattern did not. Nothing has been moved.

## 4. Other items before the tag

Decided on 2026-10-26:
- AC6.1 (Ilia): every result number is filled by a script from a committed results file,
  so the pre-test numbers in paper/pre_test.json (paper/pre_test.py) count. SPEC.md
  changed (commit 1249bb6).
- AC5.3 (Ilia): two planned test-day runs, the grid and then its controls at the grid's
  realised rates. SPEC.md records the confirmation.
- Run-length control (Ilia): RL_B3 and RL_B2b, random pulls matched per day on the
  number of pulled runs as well as the rate, added as exploratory to PREREGISTRATION.md
  sections 7 and 10 and disclosed in the Design history (commit 75f45c0). They also run in
  the second test-day run, and the summary guard refuses a run whose RL is not at the
  first run's realised rate and runs. Validation run 7ac2bbe74a19 (docs/M4_v2_draft.md):
  B3 - RL_B3 +0.0230 bp [0.0179, 0.0298], 6 of 6 days; B2b - RL_B2b +0.0165 bp
  [-0.0084, 0.0423], 4 of 6. Against rate-only R the two were +0.0278 and +0.0622, so most
  of B2b's lead over R was the run-count mismatch the audit described. Exploratory; no
  pass rule changes. Leakage audit of the run (docs/audit_run_length.md): no leak, every
  number reproduced. Its main finding: many of B3's pulled runs start just after our own
  fill on that side, when pulling costs no queue place, while RL almost always cancels a
  resting order, so B3 - RL_B3 may partly be that cost or a simple "do not rejoin the side
  just hit" rule rather than what the Hawkes direction knows. Stated next to the table and
  in the paper. Not built, Ilia's call: a control that also withholds the filled side for a
  while after each own fill, or one that copies the signals' run-length distribution and
  side persistence. Claude's recommendation: not before the tag, since these comparisons
  have no pass rule and the limitation is stated.
- Q2, Q3, Q6 (queue model API names, the exchange model with no partial fills, the third
  fee level of -0.1 bp, hypothetical before 2025-03-03) and Q24, Q26, Q29, Q30 (one
  permutation seed for C1 with three for R1; C3 removes order latency only; the C3 flag
  compares means; order latency interpolated from one-second feed samples): confirmed as
  written in PREREGISTRATION.md, chosen by Claude on Ilia's instruction of 2026-10-26 to
  pick the best option. Reason: each text states what the committed code runs, and every
  validation result was produced under it, so changing any of them now would need new
  runs and a Design history entry for no gain in what the test can show. Ilia can still
  change any of them before the tag.

Still open:
- Vivas M0 to M4 (section 2).
- /code-review of the 2026-10-26 code (section 2).
- Open questions in docs/SESSION_REPORT.md that are still Ilia's: Q32 to Q51.
- The C1 rule revision of 2026-10-26 is disclosed in the Design history; it was made
  after seeing C1 fail against B1 on the validation days.
- M5 code for v2 (2026-10-26), tested on synthetic configs, never run on a test day:
  engine/configs.v2_confirmatory (B0 to B3 in all 8 cells, C1, C2 and C4 in the primary
  cell, C3 at zero latency) and v2_confirmatory_controls (R1, R_B3, R_B2b, RL_B3 and
  RL_B2b at the first run's realised rates and, for RL, pulled runs), written by
  scripts/make_v2_configs.py confirmatory and controls. analysis.confirmatory_problem
  refuses results/summary.json unless both planned runs are present once each and every
  control is matched to its strategy. The M5 builders were reviewed in the /code-review
  of 583ccd3 onward; the RL additions were not.
- Section 11 statements and the paper print four decimals, not two (2026-10-26): with an
  MDE of 0.0231 bp, two decimals would print the MDE as 0.02. No number changes.
- The paper draft (paper/template.md, `make paper-draft`) follows the layout of
  iliaduda.com/order-book. Every pre-test number is a pre_ placeholder filled by
  paper/pre_test.py from committed results, and every test-day number a placeholder for
  results/summary.json. The draft states no test result.
- The /code-review of 583ccd3 onward found 10 issues, all fixed; the one that mattered
  most: section 9 stated s mid-sentence, so scripts/analyse.py could not read the frozen
  s. Section 9 now has the line "s = 0.0329 bp. MDE = 0.70 s = 0.0231 bp.", and
  tests/unit/test_prereg.py checks that the guard reads it.
- After the tag, by Ilia: push it, then write the first entry of DEVIATIONS.md (tag,
  commit hash, push time on GitHub).
