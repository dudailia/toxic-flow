"""Writing lint: no banned word and no em dash in any .md file or paper source.

CLAUDE.md, .claude/ and tests/writing_rules.txt are excluded: they have to name the
banned words to ban them.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = ("CLAUDE.md", ".claude/", "tests/writing_rules.txt")
EM_DASH = "—"


def banned_words() -> list[str]:
    lines = (ROOT / "tests" / "writing_rules.txt").read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def find_violations(text: str, words: list[str]) -> list[str]:
    hits = []
    for w in words:
        # \b on both sides makes it a whole-word match: "robust" does not hit "robustness".
        hits += re.findall(rf"\b{re.escape(w)}\b", text, flags=re.IGNORECASE)
    if EM_DASH in text:
        hits.append(EM_DASH)
    return hits


def linted_files() -> list[str]:
    # git's own list (tracked plus untracked, minus .gitignore) so a new file is linted
    # before its first commit, while .venv/ and data/ are skipped.
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    files = [f for f in out if f.endswith(".md") or f.startswith("paper/")]
    files = [f for f in files if not any(f == e or f.startswith(e) for e in EXCLUDED)]
    return sorted(f for f in files if (ROOT / f).is_file())


def test_find_violations_catches_word_and_dash():
    hits = find_violations("A Robust plan — ok", ["robust"])
    assert len(hits) == 2


def test_find_violations_whole_word_only():
    assert find_violations("robustness and leveraged", ["robust", "leverage"]) == []


def test_find_violations_hyphenated_word():
    assert len(find_violations("a Cutting-Edge idea", ["cutting-edge"])) == 1


def test_linted_files_include_markdown_and_skip_exclusions():
    files = linted_files()
    assert "SPEC.md" in files
    assert not any(f == "CLAUDE.md" or f.startswith(".claude/") for f in files)


@pytest.mark.parametrize("rel", linted_files())
def test_no_banned_words_or_em_dash(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert find_violations(text, banned_words()) == [], rel
