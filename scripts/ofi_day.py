#!/usr/bin/env python3
"""OFI on one converted training day: a smoke run of the B2 signal, not a tuning step.

Usage: uv run python scripts/ofi_day.py 2024-01-01
Writes docs/signals/ofi_<date>.json. For each window W in {1 s, 5 s, 30 s} it reports
OFI_W and u at 100 ms decision steps inside the quoting window, and, as a check on the
sign of the computation, the correlation of OFI_W(t) with the mid change over the same
window (t - W, t] (the relation Cont, Kukanov and Stoikov fit). Nothing here looks
beyond t, and no parameter is chosen from it.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from toxic_flow.data.book import replay_bbo
from toxic_flow.data.convert import CONVERTED
from toxic_flow.data.split_lock import assert_allowed
from toxic_flow.data.venue import venue_for
from toxic_flow.signals.ofi import ofi_contributions, ofi_signal

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_S = (1.0, 5.0, 30.0)
STEP_NS = 100_000_000


def utc_ns(day: str, hms: str) -> int:
    return int(datetime.fromisoformat(f"{day}T{hms}+00:00").timestamp()) * 10**9


def stats(x: np.ndarray) -> dict:
    q = np.percentile(x, [1, 50, 99])
    return {
        "mean": round(float(x.mean()), 4),
        "std": round(float(x.std()), 4),
        "p1": round(float(q[0]), 4),
        "p50": round(float(q[1]), 4),
        "p99": round(float(q[2]), 4),
    }


def main(day: str) -> None:
    assert_allowed(day)
    venue = venue_for(day)
    conv = json.loads((CONVERTED / day / "convert.json").read_text())
    bbo, replay = replay_bbo(
        [CONVERTED / day / f for f in conv["files"]], venue["tick_size"], venue["lot_size"]
    )
    _, e = ofi_contributions(bbo)
    # Decisions from midnight, so the 30-minute normaliser is warm by the 00:30 start.
    decisions = np.arange(utc_ns(day, "00:00:00"), utc_ns(day, "23:59:00"), STEP_NS, dtype=np.int64)
    quoting = decisions >= utc_ns(day, "00:30:00")
    row = np.searchsorted(bbo["local_ts"], decisions, side="right") - 1
    mid = np.where(row >= 0, (bbo["bid_px"][row] + bbo["ask_px"][row]) / 2, np.nan)
    out = {
        "date": day,
        "label": "smoke run on one training day; no parameter is chosen from it",
        "bbo_rows": int(len(bbo)),
        "updates_with_nonzero_e": int((e != 0).sum()),
        "replay": replay,
        "decision_steps_in_quoting_window": int(quoting.sum()),
        "windows": {},
    }
    for w in WINDOWS_S:
        u, a, ofi = ofi_signal(bbo, decisions, window_s=w)
        lag = int(w * 1e9 / STEP_NS)
        dmid = np.full(len(mid), np.nan)
        dmid[lag:] = mid[lag:] - mid[:-lag]  # the mid change over the same window
        ok = quoting & np.isfinite(dmid)
        out["windows"][f"{w:g}s"] = {
            "ofi": stats(ofi[quoting]),
            "u": stats(u[quoting]),
            "share_of_steps_with_ofi_zero": round(float((ofi[quoting] == 0).mean()), 4),
            "corr_ofi_with_same_window_mid_change": round(
                float(np.corrcoef(ofi[ok], dmid[ok])[0, 1]), 4
            ),
        }
    path = ROOT / "docs" / "signals" / f"ofi_{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
