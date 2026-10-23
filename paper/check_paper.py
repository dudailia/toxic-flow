#!/usr/bin/env python3
"""AC6.1 check: the built paper has no unresolved {{key}}, and no result section of the
template holds a literal decimal number (every result figure must be a placeholder).

Usage: uv run python paper/check_paper.py   (make paper runs it after the build)
Result sections are those whose heading starts with one of RESULT_HEADINGS.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_HEADINGS = ("Results", "Robustness", "Canaries", "Markouts")
DECIMAL = re.compile(r"(?<![\w.{])-?\d+\.\d+(?![\w.}])")
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


def result_sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) for each section whose heading starts with a result heading."""
    out, heading, body = [], None, []
    for line in text.splitlines():
        m = re.match(r"^#{2,}\s+(.*)$", line)
        if m:
            if heading and heading.startswith(RESULT_HEADINGS):
                out.append((heading, "\n".join(body)))
            heading, body = m.group(1).strip(), []
        else:
            body.append(line)
    if heading and heading.startswith(RESULT_HEADINGS):
        out.append((heading, "\n".join(body)))
    return out


def check(template: Path, built: Path) -> list[str]:
    problems = [f"unresolved placeholder {p}" for p in PLACEHOLDER.findall(Path(built).read_text())]
    for heading, body in result_sections(Path(template).read_text()):
        problems += [f"literal decimal {d} in section '{heading}'" for d in DECIMAL.findall(body)]
    return problems


def main() -> int:
    problems = check(ROOT / "paper" / "template.md", ROOT / "paper" / "build" / "paper.md")
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
