#!/usr/bin/env python3
"""Run a config that includes canary C2: the engine's run_config with the oracle hook.

Usage: uv run python tests/canary/run_c2.py configs/runs/<name>.yaml [--save-mids]
Same rules and outputs as make run (a committed config, a clean tree, results/<hash>/).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from c2_oracle import oracle_for_day  # noqa: E402

from toxic_flow.engine.run import run_config  # noqa: E402

if __name__ == "__main__":
    # --save-mids: also keep each day's mid grid for the signal-information study.
    after = None
    if "--save-mids" in sys.argv[2:]:
        from toxic_flow.data.mids import save_in_child as after
    print(run_config(Path(sys.argv[1]), oracle=oracle_for_day, after_day=after))
