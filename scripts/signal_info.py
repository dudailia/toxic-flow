#!/usr/bin/env python3
"""Exploratory signal-information study (M4 diagnosis items 6 and 7), from cached inputs:
each day's 100 ms mid (data/converted/<day>/mid_100ms.npz, saved by the diagnosis runs),
its market-order events (data/events) and OFI contributions (ofi_contributions.npz), and
the training constants (docs/signals/train_constants.json: Hawkes fit and each K).

  uv run python scripts/signal_info.py

Writes docs/exploratory/signal_information.json: per split (train, then val out of
sample), signal and horizon, the mean daily corr(u, dmid) and corr(m, |dmid|) with day
bootstrap intervals, and Hawkes minus each EWMA decay per day. Training and validation
days only; nothing is tuned here.
"""

import json
from pathlib import Path

import numpy as np

from toxic_flow.data.convert import CONVERTED
from toxic_flow.engine.run import event_inputs, ofi_inputs, utc_ns
from toxic_flow.eval.signal_info import HORIZONS_S, day_correlations, signals, summarise
from toxic_flow.signals.hawkes_fit import rescale_decay

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "exploratory" / "signal_information.json"


def hawkes_settings(params: dict) -> dict:
    def arr(p):
        return {"mu": np.array([p["mu_b"], p["mu_s"]]),
                "alpha": np.array([[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]]),
                "beta": float(p["beta"])}  # fmt: skip

    return {"B3_hawkes": arr(params)} | {
        f"C4_x{f:g}": arr(rescale_decay(params, f)) for f in (10.0, 0.1)
    }


def split_days(split: str) -> list[str]:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from make_configs import kept

    return sorted(kept(split))


def main() -> None:
    const = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())
    if const.get("label") != "train":
        raise SystemExit("training constants needed")
    hawkes = hawkes_settings(const["hawkes"]["params"])
    out = {"note": "Exploratory (M4 diagnosis items 6 and 7). Pearson correlation per day, "
                   "quoting window 00:30 to 23:59, 100 ms decision grid; mean over days with "
                   "the section 8 day bootstrap (10,000 resamples, seed 1729).",
           "splits": {}}  # fmt: skip
    for split in ("train", "val"):
        per_day = {}
        for day in split_days(split):
            f = CONVERTED / day / "mid_100ms.npz"
            if not f.exists():
                raise SystemExit(f"{f} missing: run the diagnosis runs with --save-mids")
            z = np.load(f)
            grid, mid = z["ts"], z["mid"]
            ev_ts, ev_side = event_inputs(day)
            ofi_ts, cum = ofi_inputs(day)
            sig = signals(grid, ev_ts, ev_side, ofi_ts, np.diff(cum), hawkes, const["K"])
            per_day[day] = day_correlations(mid, grid >= utc_ns(day, "00:30:00"), sig)
            print(split, day, flush=True)
        names = sorted({r["signal"] for rows in per_day.values() for r in rows})
        table = {}
        for name in names:
            for h in HORIZONS_S:
                pick = [next(r for r in rows if r["signal"] == name and r["horizon_s"] == h)
                        for rows in per_day.values()]  # fmt: skip
                table[f"{name}|{h}"] = {
                    "u": summarise([r["corr_u"] for r in pick]),
                    "m": summarise([r["corr_m"] for r in pick]),
                }
        diffs = {}
        for tau in ("1", "5", "30"):
            for h in HORIZONS_S:
                d = []
                for rows in per_day.values():
                    get = {r["signal"]: r for r in rows if r["horizon_s"] == h}
                    d.append(get["B3_hawkes"]["corr_u"] - get[f"B2b_ewma_{tau}s"]["corr_u"])
                diffs[f"B3_minus_B2b_{tau}s|{h}"] = summarise(d)
        out["splits"][split] = {"days": list(per_day), "table": table,
                                "hawkes_minus_ewma_u": diffs, "per_day": per_day}  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
