# Before the tag prereg-v1

What must happen before Ilia creates and pushes the annotated tag prereg-v1 (CLAUDE.md:
only Ilia touches tags). State as of 2026-10-26, commit given in the git log of this file.
Each item says who acts and where the material is. The order is the order to do them in.

## 0. For Ilia to decide first: Q38, the markout clock (section 6)

What it is: a markout adds its horizon h to the fill's exchange time, but reads the mid on
the decision-step grid, which runs on local time, a feed latency (a few ms) behind the
exchange clock. eval/markouts.py states this; PREREGISTRATION.md does not.

What it would change in section 6: one sentence added to the "Markouts" bullet, which
now reads "for each fill, 10,000 * side * (mid(t_fill + h) - p_fill) / p_fill ... h in
{1 s, 10 s, 60 s}". Proposed sentence: "t_fill is the fill's exchange time, and mid(t) is
the mid at the last decision step at or before t on the local clock, so the mid lags the
exchange clock by the feed latency." No code, metric or pass rule changes; markouts are a
secondary, exploratory metric.

Recommendation: add the sentence and keep the code. At horizons of 1 s and more a few ms
of offset is small, and moving the lookup to exchange time would change every markout
reported so far. Not applied, because it changes frozen text (docs/OPEN_QUESTIONS.md).

## 1. Protected-path changes

All applied on 2026-10-26, each through Ilia's permission prompt or on his instruction:

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
5. configs/repo.yaml added to .claude/protected-paths.txt (commit 36a3152, Ilia's
   instruction), so an edit of the origin the test-day lock compares against asks Ilia
   (code-review finding 1; docs/proposals/protect_repo_yaml.md).

## 2. Milestone checks and vivas

`uv run python scripts/check_milestone.py M<n>` on 2026-10-26, after the changes of this
file, including the M5 dress rehearsal (section 4):

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

/code-review of the code of 2026-10-26 (43bd486 to 681b212: the run-length control,
scripts/verify_raw.py, the check script and the fill-hold control F) found 10 issues;
docs/reviews/code_review_2026-10-26.md lists each with its outcome. Fixed with tests: F's
hold frozen and checked by the summary guard (2, 3), computed text in the generated
run-length section (4), draft sections kept (5), verify_raw on Finder metadata and nested
links (6). Applied on Ilia's instruction: configs/repo.yaml, on which the lock's origin check
rests, is now protected (1; section 1, item 5). Logged: RL and R share a random stream across controls of
different strategies (7; no single comparison is affected); two cleanups (9, 10). Finding
8 needed no change. The leakage-auditor ran on the run-length run (section 4,
docs/audit_run_length.md).

## 3. Disk for the 16 test days

Free now: 13 GB (`df -H /`, 2026-10-26 after the M5 dress rehearsal, decimal GB; it moves
with swap, between 11 and 19 GB today). The floor Ilia set is 3 GB (the watchdog stops runs below it).
Raw files may never be deleted, so all 16 test days' raw files must fit at once.

| Item | GB | Basis |
|---|---|---|
| Raw, 16 test days | about 9.9 (4.2 to 16.2) | estimate in docs/disk_budget.md: the 18 measured train and val days' mean, smallest and largest day, times 16; test-day sizes cannot be known before the tag |
| Converted cache, one day at a time | at most about 1.4 | docs/disk_budget.md, largest day at the measured ratio |
| Results of the two test-day runs | about 1.2 | measured in the M5 dress rehearsal: 61 cells a day (45 in the first run, 16 in the second) took 429 MB over the 6 validation days, about 72 MB a day, times 16; the earlier estimate from results/4db60c584c71 was 2.0 |
| Floor | 3.0 | Ilia's rule |
| Total | about 15.5 (9.8 to 21.8) | |

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
  in the paper. A control that copies the signals' run-length distribution and side
  persistence was not built.
- Fill-hold control F (Ilia, 2026-10-26, after that audit): B1 that does not rejoin the
  side just filled until the fill's exchange time plus a hold h, with h chosen on the
  training days so F's pull share matches B3's there. In PREREGISTRATION.md sections 7
  and 10 and the Design history (commit 681b212; the rule was in the code, commit ea58b7f,
  before F ran on any day). It runs in the second planned test-day run at the frozen h,
  and the summary guard refuses any other h. Training-day grid run 83bb2b991997: h = 0.1 s
  (F's pull share 0.0493 against B3's 0.0499); frozen in configs/selected.yaml and
  section 10, and tests/unit/test_prereg.py recomputes it. Validation run fb21705e1269
  (docs/M4_v2_draft.md): B3 - F +0.0021 bp [-0.0037, 0.0091], 2 of 6 days; F - RL_B3
  +0.0209 bp [0.0112, 0.0329], 6 of 6. So on the validation days most of B3's gain over
  random pulls is what not rejoining after our own fill gives, not what the Hawkes
  direction adds. Exploratory; H1 and the pass rules are unchanged. Stated in the draft and
  the paper with its limitation (6 days; the hold matches B3's training-day rate, 0.0334
  against 0.0413 on these days).
- Q2, Q3, Q6 (queue model API names, the exchange model with no partial fills, the third
  fee level of -0.1 bp, hypothetical before 2025-03-03) and Q24, Q26, Q29, Q30 (one
  permutation seed for C1 with three for R1; C3 removes order latency only; the C3 flag
  compares means; order latency interpolated from one-second feed samples): confirmed as
  written in PREREGISTRATION.md, chosen by Claude on Ilia's instruction of 2026-10-26 to
  pick the best option. Reason: each text states what the committed code runs, and every
  validation result was produced under it, so changing any of them now would need new
  runs and a Design history entry for no gain in what the test can show. Ilia can still
  change any of them before the tag.

Decided by Ilia later on 2026-10-26, all applied:
- Q34, Q35, Q36, Q50 written into PREREGISTRATION.md as he worded them, with a Design
  history entry (commit 4f6a1c5). Section 3 states that fills include those where the book
  moves through our quote with no trade at our price; each cell now records the share of
  such fills (no_print_fill_share: no opposite print at or through our price at the
  fill's exchange time, from the hashed raw trades, commit 19347d5), and the summary and
  the paper report it for every day. Section 8: selectivity is the median over test days
  of the daily ratio. Section 10: pass rules use the 95% percentile bootstrap, 10,000
  resamples, seed 1729. Section 11: a row for bootstrap and t intervals that disagree
  about 0, printed word for word by eval/bootstrap.conclusion whatever the size of the
  mean; a test checks that every statement the code can print is a section 11 row.
- Q37 and Q40 applied as recommended, since they change no frozen text. Q38 is open
  (section 0). docs/OPEN_QUESTIONS.md has each answer.
- C3 flag revised (commit 36e0bb7): a non-zero-latency run of B3 flags only if it beats
  the zero-latency run by more than the MDE on the mean, or with a bootstrap interval for
  the daily difference that excludes 0. Section 10 and the Design history. Prompted by the
  dress rehearsal below.
- The paper has control F as its own exploratory section, "Control F: not rejoining the
  side just filled", with the validation result and five limitations next to it: 6 days
  that also chose B3's settings; F's pull share matched on training days but not on these
  (pre_f_share keys); F built after an audit of these days, so they cannot test it;
  primary cell only; simulated fills.

M5 dress rehearsal (2026-10-26): the whole test-day pipeline on the 6 validation days in
place of the test days, output in the session scratchpad only, deleted afterwards; no
number from it is in the repo. A driver (outside the repo) ran the real code in separate
steps and redirected only paths: make_v2_configs.py confirmatory and controls (the test
split read as the validation days), run 1 through run_c2.py's oracle, run 2, analyse.py
summary with its guards (only the tag-ancestry check answered yes, since no tag exists),
and the paper steps (pre_test, build_paper, figures, check_paper). Run 1 took 71 minutes
for 270 cells and run 2 41 minutes for 96 cells, so about 5 hours for 16 test days of the
same size; 429 MB of results. Every guard passed: both planned runs present once each,
every control at its strategy's realised rate and runs, F at the frozen hold, s equal to
section 9, config hashes equal to the configs. The rehearsal's numbers equal the
committed validation runs where they overlap (C1 - R1, C2 - B1, B3 - RL_B3, B3 - F), so
the test-day config builders give the strategies the validation runs used. Found and
fixed, each with a test:
1. A full fill or step buffer stopped recording silently, which would corrupt every
   metric of a cell; the busiest training cell had 169,550 fills against a 500,000 buffer.
   A cell now stops if a buffer is full or the recorded fills differ from hftbacktest's
   count (equal in every committed run and every rehearsal cell); buffer 2,000,000
   (commit fbe7f45).
2. The C3 flag fired on noise: B3 at low latency beat zero latency on the mean by a
   noise-level margin. The leakage-auditor found no leak (toxic decisions identical at
   all latencies, the zero and high rows equal to results/5d27bc8ae820). Rule revised by
   Ilia (above).
3. The one-page summary printed the test result without its limitations paragraph, and
   its axis labels were cut at the page edge and overlapped (commit 3efca19).
4. The README test-run steps lacked the commits the run needs: run_config refuses an
   uncommitted config or a changed tree, and AC5.2 needs the exclusion record committed
   before the first run (commit 761168c).
Not reachable by the rehearsal: the test-day lock and download, the exclusion step on
test days, and analyse.py's check that each run's commit follows the tag.

Still open:
- Q38, the markout clock (section 0).
- Vivas M0 to M4 (section 2).
- The C1 rule revision of 2026-10-26 is disclosed in the Design history; it was made
  after seeing C1 fail against B1 on the validation days.
- M5 code for v2 (2026-10-26), tested on synthetic configs and run end to end on the
  validation days in the dress rehearsal (section 4), never run on a test day:
  engine/configs.v2_confirmatory (B0 to B3 in all 8 cells, C1, C2 and C4 in the primary
  cell, C3 at zero latency) and v2_confirmatory_controls (R1, R_B3, R_B2b, RL_B3 and
  RL_B2b at the first run's realised rates and, for RL, pulled runs, and F at the frozen
  hold), written by
  scripts/make_v2_configs.py confirmatory and controls. analysis.confirmatory_problem
  refuses results/summary.json unless both planned runs are present once each and every
  control is matched to its strategy. Reviewed in the /code-review of 583ccd3 onward and,
  with RL and F, in that of 2026-10-26 (section 2).
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
