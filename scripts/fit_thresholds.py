#!/usr/bin/env python3
"""Overlay thresholds from the training days (PREREGISTRATION.md section 5, v2).

  uv run python scripts/fit_thresholds.py

For every signal and parameter of the tuning grid (B2 at W = 1, 5, 30 s, B2b at
tau = 1, 5, 30 s, B3 at the fitted beta) and the two C4 decays: u and m at every 100 ms
decision step of each training day's quoting window, from the same offline functions the
strategy loops are tested against, with K from docs/signals/train_constants.json. The
days are pooled: theta_u(p) is the (1 - p) quantile of |u| for p in {0.05, 0.10, 0.25,
0.50}, theta_m the 0.90 quantile of m. Also written: the share of steps above each
threshold, pooled (the check of section 5) and per day. Training days only.
Writes docs/signals/train_thresholds.json.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_configs import kept  # noqa: E402
from signal_info import hawkes_settings  # noqa: E402

from toxic_flow.data.split_lock import assert_allowed  # noqa: E402
from toxic_flow.engine.run import event_inputs, ofi_inputs, utc_ns  # noqa: E402
from toxic_flow.eval.signal_info import signals  # noqa: E402
from toxic_flow.signals.thresholds import (  # noqa: E402
    MAGNITUDE_Q,
    PULL_RATES,
    share_above,
    theta_m,
    theta_u,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "signals" / "train_thresholds.json"
STEP_NS = 100_000_000


def day_signals(day: str, const: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{setting: (|u|, m)} over the day's quoting window, float32 to keep 12 days in memory
    (the rounding is below 1e-7 relative; the slow test checks the shares in float64)."""
    grid = np.arange(utc_ns(day, "00:00:00"), utc_ns(day, "23:59:00"), STEP_NS, dtype=np.int64)
    quoting = grid >= utc_ns(day, "00:30:00")
    ev_ts, ev_side = event_inputs(day)
    ofi_ts, cum = ofi_inputs(day)
    hawkes = hawkes_settings(const["hawkes"]["params"])
    sig = signals(grid, ev_ts, ev_side, ofi_ts, np.diff(cum), hawkes, const["K"])
    return {k: (np.abs(u[quoting]).astype(np.float32), m[quoting].astype(np.float32))
            for k, (u, m) in sig.items()}  # fmt: skip


def main() -> None:
    const = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    if const.get("label") != "train":
        raise SystemExit("training constants needed")
    days = sorted(kept("train"))
    per_day = {}
    for day in days:
        assert_allowed(day)
        per_day[day] = day_signals(day, const)
        print(day, flush=True)
    out = {"label": "train", "days": days, "pull_rates": list(PULL_RATES),
           "magnitude_quantile": MAGNITUDE_Q, "signals": {}}  # fmt: skip
    for name in per_day[days[0]]:
        u = np.concatenate([per_day[d][name][0] for d in days]).astype(np.float64)
        m = np.concatenate([per_day[d][name][1] for d in days]).astype(np.float64)
        th_u = {f"{p:g}": theta_u(u, p) for p in PULL_RATES}
        th_m = theta_m(m)
        out["signals"][name] = {
            "theta_u": th_u,
            "theta_m": th_m,
            "steps": len(u),
            "share_above": {k: share_above(u, v) for k, v in th_u.items()},
            "share_m_above": share_above(m, th_m),
            "share_above_by_day": {
                d: {
                    k: share_above(per_day[d][name][0].astype(np.float64), v)
                    for k, v in th_u.items()
                }
                for d in days
            },  # fmt: skip
        }
        print(name, {k: round(v, 4) for k, v in th_u.items()}, round(th_m, 4), flush=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
