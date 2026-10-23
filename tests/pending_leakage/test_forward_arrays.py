"""AC3.6: the oracle canary C2 under tests/canary/ is the only code that builds a
forward-looking array; no strategy or signal file names one. Pending: to move into
tests/leakage/ (protected) by Ilia."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORWARD = re.compile(r"\bfuture_mid\b|\bforward_\w+")


def test_no_strategy_or_signal_file_names_a_forward_array():
    hits = [
        p.relative_to(ROOT).as_posix()
        for d in ("src/toxic_flow/strategies", "src/toxic_flow/signals")
        for p in (ROOT / d).rglob("*.py")
        if FORWARD.search(p.read_text())
    ]
    assert not hits, hits


def test_only_tests_canary_builds_the_oracle_series():
    src = [
        p
        for p in (ROOT / "src").rglob("*.py")
        if "tests.canary" in p.read_text() or "c2_oracle" in p.read_text()
    ]
    assert not src, src
    assert FORWARD.search((ROOT / "tests" / "canary" / "c2_oracle.py").read_text())
