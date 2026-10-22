#!/usr/bin/env python3
"""Stop hook: run make check when the working tree has changes.

On failure, block the stop and feed the tail of the output back to Claude. After the
third consecutive failure in a session, let Claude stop so Ilia can step in. That matches
the CLAUDE.md rule: two failed corrections, then stop and tell Ilia.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
MAX_BLOCKS = 3


def main() -> None:
    event = json.load(sys.stdin)
    session = event.get("session_id", "unknown")
    state = ROOT / ".claude" / "state"
    state.mkdir(parents=True, exist_ok=True)
    counter = state / f"stop-failures-{session}"

    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True
    )
    if not status.stdout.strip():
        counter.unlink(missing_ok=True)
        sys.exit(0)  # clean tree: the pre-commit hook already ran make check

    r = subprocess.run(["make", "-C", str(ROOT), "check"], capture_output=True, text=True)
    if r.returncode == 0:
        counter.unlink(missing_ok=True)
        sys.exit(0)

    failures = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(failures))
    tail = (r.stdout + r.stderr)[-6000:]
    if failures >= MAX_BLOCKS:
        msg = f"make check failed {failures} times in a row. Stopping so Ilia can look."
        print(json.dumps({"systemMessage": msg}))
        sys.exit(0)
    reason = (
        f"make check failed (failure {failures}; you get {MAX_BLOCKS - 1} corrections). "
        f"Fix the cause, not the test.\n\n{tail}"
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
