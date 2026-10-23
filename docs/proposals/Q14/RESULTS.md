# Q14: stricter test-day lock (proposal)

Ilia approved these diffs on 2026-10-22 but asked that no protected path be edited in this
block. The two files here are complete replacements:

- `split_lock.py` replaces `src/toxic_flow/data/split_lock.py`.
- `test_split_lock.py` replaces `tests/leakage/test_split_lock.py`.

`configs/repo.yaml` (not protected) is already committed with
`origin: https://github.com/dudailia/toxic-flow.git`, the URL `git remote get-url origin`
prints in this checkout.

## What changes

The lock opens a test day only when all three hold:

- (a) prereg-v1 is an annotated tag: `git cat-file -t refs/tags/prereg-v1` prints `tag`.
- (b) `git remote get-url origin` equals `origin` in configs/repo.yaml, read from the repo
  being checked. A missing or unreadable configs/repo.yaml keeps the lock closed.
- (c) the hash `git ls-remote --tags origin prereg-v1` returns equals the local tag object
  hash. This was already enforced before the change.

## How it was tested

In a fresh clone of the repo at commit 76ae21a (scratchpad copy, with configs/repo.yaml
copied in), run against the clone's own `src/` through `PYTHONPATH`:

1. The proposed test file with the CURRENT lock. Three new tests fail: the lightweight
   tag, the origin other than configs/repo.yaml, and the missing configs/repo.yaml. The
   new test for (c), a remote tag replaced by another object, passes, because the current
   lock already compares hashes; so does the older `test_local_tag_differs_from_remote_refuses`.
2. The proposed test file with the PROPOSED lock: all 15 pass.
3. The whole fast suite of the clone with the PROPOSED lock: all pass.

```text
=== RUN 1: proposed tests, CURRENT lock (src/toxic_flow/data/split_lock.py at 76ae21a)
lock module: /private/tmp/claude-501/-Users-iliaduda-Projects-toxic-flow/344a1151-4baf-4164-8bf1-2eb83851dc7e/scratchpad/q14/src/toxic_flow/data/split_lock.py
rootdir: /private/tmp/claude-501/-Users-iliaduda-Projects-toxic-flow/344a1151-4baf-4164-8bf1-2eb83851dc7e/scratchpad/q14
tests/leakage/test_split_lock.py::test_no_tag_refuses_test_day PASSED    [  6%]
tests/leakage/test_split_lock.py::test_local_tag_only_refuses_test_day PASSED [ 13%]
tests/leakage/test_split_lock.py::test_tag_on_both_allows_test_day PASSED [ 20%]
tests/leakage/test_split_lock.py::test_train_and_val_days_allowed_without_tag PASSED [ 26%]
tests/leakage/test_split_lock.py::test_missing_remote_refuses PASSED     [ 33%]
tests/leakage/test_split_lock.py::test_local_tag_differs_from_remote_refuses PASSED [ 40%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[2025-07-01T00:00:00] PASSED [ 46%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[20250701] PASSED [ 53%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[day2] PASSED [ 60%]
tests/leakage/test_split_lock.py::test_date_outside_every_split_refused[2025-07-02] PASSED [ 66%]
tests/leakage/test_split_lock.py::test_date_outside_every_split_refused[not-a-date] PASSED [ 73%]
tests/leakage/test_split_lock.py::test_lightweight_tag_refuses_test_day FAILED [ 80%]
tests/leakage/test_split_lock.py::test_origin_other_than_the_configured_repo_refuses FAILED [ 86%]
tests/leakage/test_split_lock.py::test_remote_tag_replaced_with_another_object_refuses PASSED [ 93%]
tests/leakage/test_split_lock.py::test_missing_repo_config_refuses FAILED [100%]
FAILED tests/leakage/test_split_lock.py::test_lightweight_tag_refuses_test_day
FAILED tests/leakage/test_split_lock.py::test_origin_other_than_the_configured_repo_refuses
FAILED tests/leakage/test_split_lock.py::test_missing_repo_config_refuses - A...
========================= 3 failed, 12 passed in 5.06s =========================
```

```text
=== RUN 2: proposed tests, PROPOSED lock (docs/proposals/Q14/split_lock.py copied into src/)
lock module: /private/tmp/claude-501/-Users-iliaduda-Projects-toxic-flow/344a1151-4baf-4164-8bf1-2eb83851dc7e/scratchpad/q14/src/toxic_flow/data/split_lock.py
project repo tag_published: False
tests/leakage/test_split_lock.py::test_no_tag_refuses_test_day PASSED    [  6%]
tests/leakage/test_split_lock.py::test_local_tag_only_refuses_test_day PASSED [ 13%]
tests/leakage/test_split_lock.py::test_tag_on_both_allows_test_day PASSED [ 20%]
tests/leakage/test_split_lock.py::test_train_and_val_days_allowed_without_tag PASSED [ 26%]
tests/leakage/test_split_lock.py::test_missing_remote_refuses PASSED     [ 33%]
tests/leakage/test_split_lock.py::test_local_tag_differs_from_remote_refuses PASSED [ 40%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[2025-07-01T00:00:00] PASSED [ 46%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[20250701] PASSED [ 53%]
tests/leakage/test_split_lock.py::test_other_spellings_of_a_test_date_refused[day2] PASSED [ 60%]
tests/leakage/test_split_lock.py::test_date_outside_every_split_refused[2025-07-02] PASSED [ 66%]
tests/leakage/test_split_lock.py::test_date_outside_every_split_refused[not-a-date] PASSED [ 73%]
tests/leakage/test_split_lock.py::test_lightweight_tag_refuses_test_day PASSED [ 80%]
tests/leakage/test_split_lock.py::test_origin_other_than_the_configured_repo_refuses PASSED [ 86%]
tests/leakage/test_split_lock.py::test_remote_tag_replaced_with_another_object_refuses PASSED [ 93%]
tests/leakage/test_split_lock.py::test_missing_repo_config_refuses PASSED [100%]
============================== 15 passed in 5.30s ==============================
=== RUN 3: whole fast suite in the copy, PROPOSED lock
117 passed, 4 deselected in 10.00s
```

## To apply

```bash
cp docs/proposals/Q14/split_lock.py src/toxic_flow/data/split_lock.py
cp docs/proposals/Q14/test_split_lock.py tests/leakage/test_split_lock.py
make check
```

Both targets are protected, so each copy is Ilia's own edit. SPEC.md M0 should then say
the lock checks (a), (b) and (c); that is a one-line change outside the protected list.

## Proposed addition to .claude/protected-paths.txt

`configs/repo.yaml` now decides which remote can open the lock, so an edit to it should
prompt Ilia like the other guards. Proposed line, to add by hand:

```text
configs/repo.yaml
```
