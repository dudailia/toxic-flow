#!/usr/bin/env python3
"""Exploratory configs for the M4 diagnosis (Ilia, 2026-10-24): not pre-registered runs.

  uv run python scripts/make_diag_configs.py

diag_val (validation days): B1 at the selected setting and at gamma 0.2, 20 min (the
first choice, item 4); C2 and C2 with u flipped (item 1); B1 and C2 in the log queue
model at zero latency (item 2). Primary cell unless stated.
diag_train (training days): B1 at both settings (item 4); the join-the-touch base T0 in
all 8 cells (items 5 and 9); C2 on that base in the primary cell (item 5).
Both run with tests/canary/run_c2.py --save-mids, since they include C2.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_configs import ROOT, kept  # noqa: E402

from toxic_flow.engine import configs  # noqa: E402

PRIMARY = [configs.PRIMARY]
EASY = [["log", "zero"]]  # the most optimistic queue model at zero latency (item 2)


def main() -> None:
    selected = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
    b1 = configs._b1(selected)
    first = {"gamma": 0.2, "window_s": 1200, "update_every": 50}
    val = [
        {"name": "B1", **b1, "cells": PRIMARY},
        {"name": "B1", **first, "label": "B1_g0.2", "cells": PRIMARY},
        {"name": "C2", **b1, "cells": PRIMARY},
        {"name": "C2", **b1, "label": "C2_flip", "flip": True, "cells": PRIMARY},
        {"name": "B1", **b1, "label": "B1_easy", "cells": EASY},
        {"name": "C2", **b1, "label": "C2_easy", "cells": EASY},
    ]
    train = [
        {"name": "B1", **b1, "cells": PRIMARY},
        {"name": "B1", **first, "label": "B1_g0.2", "cells": PRIMARY},
        {"name": "B1", **b1, "label": "T0", "touch": True},  # all 8 cells
        {"name": "C2", **b1, "label": "C2_touch", "touch": True, "cells": PRIMARY},
    ]
    for name, split, strategies in (("diag_val", "val", val), ("diag_train", "train", train)):
        cfg = configs._config(name, kept(split), strategies, configs.ALL_QUEUES, ["low", "high"])
        out = ROOT / "configs" / "runs" / f"{name}.yaml"
        if out.exists():
            raise SystemExit(f"{out} exists; a changed config needs a new name")
        out.write_text(
            "# Written by scripts/make_diag_configs.py. Exploratory (M4 diagnosis).\n"
            + yaml.safe_dump(cfg, sort_keys=False)
        )
        print(out)


if __name__ == "__main__":
    main()
