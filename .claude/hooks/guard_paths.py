#!/usr/bin/env python3
"""PreToolUse guard for Edit, Write and NotebookEdit.

Denies writes under data/raw/ and results/, denies edits to PREREGISTRATION.md once tag
prereg-v1 exists, and asks Ilia before any edit to a path in .claude/protected-paths.txt.
Prints a JSON decision on stdout and exits 0; prints nothing when it has no objection.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def decide(kind: str, reason: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def tag_exists(name: str = "prereg-v1") -> bool:
    r = subprocess.run(
        ["git", "-C", str(ROOT), "tag", "--list", name], capture_output=True, text=True
    )
    return r.stdout.strip() == name


def protected_entries() -> list[str]:
    f = ROOT / ".claude" / "protected-paths.txt"
    if not f.exists():
        return []
    lines = [ln.strip() for ln in f.read_text().splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        sys.exit(0)
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or ROOT) / path
    try:
        rel = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        sys.exit(0)  # outside the repo; normal permission rules apply

    if rel.startswith("data/raw/"):
        decide("deny", "data/raw/ is immutable. Only the downloader writes there.")
    if rel.startswith("results/"):
        decide("deny", "results/ is written only by make run from a committed config.")
    if rel == "PREREGISTRATION.md" and tag_exists():
        decide("deny", "PREREGISTRATION.md is frozen at prereg-v1. Use DEVIATIONS.md.")
    for entry in protected_entries():
        hit = rel.startswith(entry) if entry.endswith("/") else rel == entry
        if hit:
            decide("ask", f"{rel} is a leakage guard. Ilia approves this edit himself.")
    sys.exit(0)


if __name__ == "__main__":
    main()
