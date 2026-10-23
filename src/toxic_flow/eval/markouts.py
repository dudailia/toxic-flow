"""Per-fill markouts (PREREGISTRATION.md section 6), computed after the run, never inside it.

markout_h = 10,000 * side * (mid(t_fill + h) - p_fill) / p_fill, side +1 for a buy. The mid
at t_fill + h is the one recorded at the last decision step at or before that time.
Negative means adverse selection.
"""

import numpy as np

HORIZONS_S = (1, 10, 60)


def markouts(fills: np.ndarray, steps: np.ndarray, horizons_s=HORIZONS_S) -> dict:
    out = {}
    for h in horizons_s:
        at = fills["exch_ts"] + int(h * 1e9)
        i = np.searchsorted(steps["ts"], at, side="right") - 1
        mid = np.where(
            (i >= 0) & (at <= steps["ts"][-1]), steps["mid"][np.clip(i, 0, None)], np.nan
        )
        out[f"markout_{h}s_bps"] = 1e4 * fills["side"] * (mid - fills["price"]) / fills["price"]
    return out
