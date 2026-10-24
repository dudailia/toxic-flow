#!/usr/bin/env python3
"""make run, with each day's M1 files written from the run's own conversion.

Usage: uv run python scripts/run_with_m1.py configs/runs/<name>.yaml
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_day import m1  # noqa: E402

from toxic_flow.engine.run import run_config  # noqa: E402

if __name__ == "__main__":
    print(run_config(Path(sys.argv[1]), after_day=m1))
