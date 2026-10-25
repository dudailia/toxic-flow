#!/usr/bin/env python3
"""Exploratory configs for the M4 diagnosis (Ilia, 2026-10-24): not pre-registered runs.

  uv run python scripts/make_diag_configs.py

diag_val (validation days): B1 at the selected setting and at gamma 0.2, 20 min (the
first choice, item 4); C2 and C2 with u flipped (item 1); B1 and C2 in the log queue
model at zero latency (item 2). Primary cell unless stated.
diag_train (training days): B1 at both settings (item 4); the join-the-touch base T0 in
all 8 cells (items 5 and 9); C2 on that base in the primary cell (item 5). Superseded
before it ran by diag_train_touch, which adds the B3 and B2b grids on the touch base
(items 10 and 11) so the 12 training days are converted once; the B2 grid on that base
is a separate run (diag_train_touch_b2) for time.
Both run with tests/canary/run_c2.py --save-mids, since they include C2.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from itertools import product  # noqa: E402

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

    const = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    grid = {"B2b": [], "B3": [], "B2": []}
    for c, d in product(configs.C_GRID, configs.D_GRID):
        grid["B3"].append(configs._overlay("B3", b1, c, d, const))
        for t in configs.TAUS_S:
            grid["B2b"].append(configs._overlay("B2b", b1, c, d, const, tau_s=t))
        for w in configs.OFI_WINDOWS_S:
            grid["B2"].append(configs._overlay("B2", b1, c, d, const, ofi_window_s=w))
    touch = {"touch": True, "cells": PRIMARY}
    train_touch = train + [s | touch | {"label": f"{s['name']}_touch"}
                           for s in grid["B3"] + grid["B2b"]]  # fmt: skip
    b2_touch = [s | touch | {"label": "B2_touch"} for s in grid["B2"]]
    runs = (("diag_val", "val", val), ("diag_train_touch", "train", train_touch),
            ("diag_train_touch_b2", "train", b2_touch))  # fmt: skip
    for name, split, strategies in runs:
        if (ROOT / "configs" / "runs" / f"{name}.yaml").exists():
            continue
        cfg = configs._config(name, kept(split), strategies, configs.ALL_QUEUES, ["low", "high"])
        out = ROOT / "configs" / "runs" / f"{name}.yaml"
        out.write_text(
            "# Written by scripts/make_diag_configs.py. Exploratory (M4 diagnosis).\n"
            + yaml.safe_dump(cfg, sort_keys=False)
        )
        print(out)


if __name__ == "__main__":
    main()
