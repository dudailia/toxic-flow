#!/usr/bin/env python3
"""Fill paper/template.md into paper/build/paper.md.

Usage: uv run python paper/build_paper.py           (make paper)
       uv run python paper/build_paper.py --draft   (make paper-draft)

Keys starting with pre_ come from paper/pre_test.json (paper/pre_test.py: training and
validation days only); every other {{key}} comes from results/summary.json, the test-day
analysis. A missing key stops the build. Floats are printed with four decimals (the MDE
is a few hundredths of a bp), other values as they are. These two files are the only
sources of numbers, so the paper cannot state a figure no committed result produced.

--draft fills the pre_ keys only and writes paper/build/draft.md with every test-day key
left as a visible {{key}}: the page before the test days exist, which states no test
result.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
PRE = "pre_"


def render(value) -> str:
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def values(summary: Path | None, pre: Path | None) -> dict:
    """pre_ keys from pre, the rest from summary; a key in the wrong file is refused, so a
    test-day number can never come from the pre-test file or the other way round."""
    out = {}
    if pre is not None:
        p = json.loads(Path(pre).read_text())
        out |= {k: v for k, v in p.items() if k.startswith(PRE)}
    if summary is not None:
        s = json.loads(Path(summary).read_text())
        wrong = sorted(k for k in s if k.startswith(PRE))
        if wrong:
            raise KeyError(f"{summary} holds pre-test keys: {wrong}")
        out |= s
    return out


def build(template: Path, summary: Path | None, out: Path, pre: Path | None = None,
          draft: bool = False) -> Path:  # fmt: skip
    vals = values(summary, pre)
    text = Path(template).read_text()
    keys = set(PLACEHOLDER.findall(text))
    need = {k for k in keys if k.startswith(PRE)} if draft else keys
    missing = sorted(k for k in need if k not in vals)
    if missing:
        raise KeyError(f"not in {summary if not draft else pre}: {missing}")

    def fill(m):
        k = m.group(1)
        return m.group(0) if draft and not k.startswith(PRE) else render(vals[k])

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PLACEHOLDER.sub(fill, text))
    return out


def main() -> int:
    draft = "--draft" in sys.argv[1:]
    template, pre = ROOT / "paper" / "template.md", ROOT / "paper" / "pre_test.json"
    if draft:
        print(build(template, None, ROOT / "paper" / "build" / "draft.md", pre, draft=True))
        return 0
    summary = ROOT / "results" / "summary.json"
    if not summary.exists():
        print("no results/summary.json yet: it is written once the confirmatory runs exist")
        return 1
    print(build(template, summary, ROOT / "paper" / "build" / "paper.md", pre))
    return 0


if __name__ == "__main__":
    sys.exit(main())
