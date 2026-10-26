# /code-review of 2026-10-26 (43bd486..681b212, src scripts tests)

Scope: the run-length control RL, scripts/verify_raw.py, the scripts/check_milestone.py
changes, and the fill-hold control F, as Ilia asked. 10 findings; each below with what was
done. "Could change a conclusion" is the test Ilia set: those are fixed with a test.

| # | Finding | Could change a conclusion? | Outcome |
|---|---|---|---|
| 1 | The lock's check (b) reads the expected origin from configs/repo.yaml, which is not protected | No result, but it weakens the test-day lock | Logged as docs/proposals/protect_repo_yaml.md: add configs/repo.yaml to .claude/protected-paths.txt (Ilia's file) |
| 2 | configs/selected.yaml has no F hold, and the builders failed with KeyError; a docstring named a subcommand that does not exist | It blocked the second test-day run | Fixed: configs.frozen_hold stops with a clear message unless F's hold is one of the grid's; the hold is written to configs/selected.yaml from scripts/m4_v2.py fillhold, and a test checks it against the rule on the committed training run; docstring fixed. Tests: test_f_needs_a_frozen_hold_from_the_grid, test_prereg |
| 3 | The summary guard did not check F's hold | Yes: a hand-edited hold would reach the paper as if pre-registered | Fixed: analysis.confirmatory_problem refuses F at any hold but the frozen one, which scripts/analyse.py reads through configs.frozen_hold. Test: test_the_guard_wants_f_at_the_frozen_hold |
| 4 | scripts/m4_v2.py runlength printed fixed conclusions ("inconclusive", "Six") | Yes, on any other run | Fixed: the interval verdict and the day count are computed; the audit's finding is printed only next to the audited run's hash (audit_note), otherwise the section says that run has no audit. Checked by regenerating the section |
| 5 | Draft sections could be duplicated or dropped by the order the subcommands run in; `report` overwrote the whole draft | It loses tables, not numbers | Fixed: put_section replaces one section by its heading and keeps the others in a fixed order; `report` keeps them too and stops rather than overwrite the reading written by hand at the top. Checked: random and runlength rerun leave the draft byte for byte the same |
| 6 | verify_raw.py failed on macOS metadata files and did not flag links inside raw | It could block the SSD switch | Fixed: .DS_Store and ._* are skipped, a link inside raw is a problem. Test: test_finder_metadata_is_ignored_and_a_link_inside_is_flagged |
| 7 | RL and R seed the generator alike, so RL_B3_sk, RL_B2b_sk and R_*_sk on a day share one uniform stream | No: each comparison uses one control, whose three seeds are independent of each other; the shared stream only links controls of different strategies, which are compared only in the exploratory RL - R rows | Logged, not changed: a change would make results/7ac2bbe74a19 no longer reproduce from the code. If Ilia wants independent streams on the test days, add the control's name to the seed and rerun the run-length validation run (about 40 minutes) before the tag |
| 8 | AC4.2 uses n = 16, scripts/analyse.py mde the kept test days | No | No change: section 9 fixes n = 16 before the tag and says the MDE is recomputed with the same s if exclusions reduce n, which is what each does |
| 9 | hold_ns added by hand to four positional argument tuples in engine/run.py._touch_args | No: test_f_holds_a_side_in_the_loop_arguments and the loop tests check the positions | Logged as cleanup |
| 10 | realised_rates read twice in make_v2_configs.py | No | Logged as cleanup |
