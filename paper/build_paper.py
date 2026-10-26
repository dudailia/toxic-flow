#!/usr/bin/env python3
"""Fill paper/template.md from results/summary.json into paper/build/paper.md.

Usage: uv run python paper/build_paper.py   (make paper)

Every {{key}} in the template must be a key in the summary; a missing key stops the build.
Floats are printed with four decimals (the MDE is a few hundredths of a bp), other values
as they are. The summary is the only
source of numbers, so the paper cannot state a figure no committed result produced.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def render(value) -> str:
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def build(template: Path, summary: Path, out: Path) -> Path:
    values = json.loads(Path(summary).read_text())
    text = Path(template).read_text()
    missing = sorted({k for k in PLACEHOLDER.findall(text) if k not in values})
    if missing:
        raise KeyError(f"not in {summary}: {missing}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PLACEHOLDER.sub(lambda m: render(values[m.group(1)]), text))
    return out


def main() -> int:
    summary = ROOT / "results" / "summary.json"
    if not summary.exists():
        print("no results/summary.json yet: it is written once the confirmatory runs exist")
        return 1
    print(build(ROOT / "paper" / "template.md", summary, ROOT / "paper" / "build" / "paper.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
