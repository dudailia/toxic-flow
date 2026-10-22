#!/usr/bin/env python3
"""PostToolUse hook: ruff format and ruff check --fix on an edited .py file.

Exit 2 shows remaining lint errors to Claude so it fixes them; the edit itself already ran.
"""

import json
import subprocess
import sys


def main() -> None:
    event = json.load(sys.stdin)
    path = (event.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        sys.exit(0)
    subprocess.run(["uv", "run", "ruff", "format", path], capture_output=True)
    r = subprocess.run(
        ["uv", "run", "ruff", "check", "--fix", path], capture_output=True, text=True
    )
    if r.returncode != 0:
        sys.stderr.write((r.stdout + r.stderr)[-4000:])
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
