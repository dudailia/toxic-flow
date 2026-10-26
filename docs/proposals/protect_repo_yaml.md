# Proposal: protect configs/repo.yaml

From the /code-review of 2026-10-26 (docs/reviews/code_review_2026-10-26.md, finding 1).
Applied on 2026-10-26 on Ilia's instruction: configs/repo.yaml is now a line in
.claude/protected-paths.txt, and the guard hook asks Ilia before any edit to it.

Since Q14 (commit 3d98a41), the test-day lock opens a test day only if `git remote get-url
origin` equals `origin` in configs/repo.yaml. src/toxic_flow/data/split_lock.py is
protected, but configs/repo.yaml is not. So an edit to configs/repo.yaml that names a
local bare repo, with origin pointed there and an annotated prereg-v1 pushed to it, passes
all three checks without any public tag, and the edit does not prompt Ilia. Check (b) was
added to stop exactly that.

Proposed: add one line to .claude/protected-paths.txt:

    configs/repo.yaml

Then any edit of the configured origin prompts Ilia, like an edit of the lock itself. The
alternative, a constant in split_lock.py, needs both protected lock files changed (the
tests in tests/leakage/test_split_lock.py write a repo.yaml for their throwaway origin),
and buys nothing over protecting the file.

Effect on results: none. No test day has been requested, and the lock is closed on this
checkout (no tag).
