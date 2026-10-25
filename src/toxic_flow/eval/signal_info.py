"""Do the signals carry information, before any quoting? (M4 diagnosis items 6 and 7,
exploratory.) Forward-looking by design, so it lives in eval only.

For each signal and parameter setting, at every 100 ms decision time t in the quoting
window, the causal direction u(t) and magnitude m(t) are computed with the same offline
functions the overlay loop is tested against (signals/), and compared with the mid change
over the next h seconds: corr(u, mid(t + h) - mid(t)) and corr(m, |mid(t + h) - mid(t)|),
one Pearson correlation per day. Days are then summarised by the mean daily correlation
with the day-level bootstrap of section 8.
"""

import numpy as np

from toxic_flow.eval.bootstrap import bootstrap_ci
from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_online import hawkes_signal
from toxic_flow.signals.normalise import NORM_STEPS, magnitude, trailing_mean
from toxic_flow.signals.ofi import ofi_window, trailing_std

HORIZONS_S = (1, 5, 10)
STEP_S = 0.1


def future_change(mid: np.ndarray, h_s: float) -> np.ndarray:
    """mid(t + h) - mid(t) on the 100 ms grid; NaN where t + h is past the end."""
    k = int(round(h_s / STEP_S))
    out = np.full(len(mid), np.nan)
    out[:-k] = mid[k:] - mid[:-k]
    return out


def signals(grid, ev_ts, ev_side, ofi_ts, ofi_e, hawkes: dict, K: dict) -> dict:
    """{name: (u, m)} at each grid time for every setting of the tuning grid (section 4)
    and the two C4 decays. K holds each setting's constant from the training days."""
    out = {}
    for w in (1.0, 5.0, 30.0):
        ofi = ofi_window(ofi_ts, ofi_e, grid, w)
        s = trailing_std(ofi, NORM_STEPS)
        with np.errstate(divide="ignore", invalid="ignore"):
            u = np.where(s > 0, np.tanh(ofi / s), 0.0)
        a = np.abs(ofi)
        out[f"B2_ofi_{w:g}s"] = (u, a)
    for tau in (1.0, 5.0, 30.0):
        out[f"B2b_ewma_{tau:g}s"] = ewma_at(ev_ts, ev_side, grid, tau)
    for name, p in hawkes.items():
        out[name] = hawkes_signal(ev_ts, ev_side, grid, p["mu"], p["alpha"], p["beta"])
    return {
        name: (u, magnitude(a, trailing_mean(a, NORM_STEPS), K[name]))
        for name, (u, a) in out.items()
    }


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def day_correlations(mid, quoting, sig: dict) -> list[dict]:
    """One row per signal and horizon for one day: corr(u, dmid) and corr(m, |dmid|)."""
    rows = []
    for h in HORIZONS_S:
        d = future_change(mid, h)
        for name, (u, m) in sig.items():
            rows.append({"signal": name, "horizon_s": h,
                         "corr_u": _corr(u[quoting], d[quoting]),
                         "corr_m": _corr(m[quoting], np.abs(d[quoting]))})  # fmt: skip
    return rows


def summarise(daily: list[float]) -> dict:
    """Mean daily correlation, day bootstrap 95% interval, and days with it above 0."""
    d = np.asarray([x for x in daily if np.isfinite(x)])
    ci = bootstrap_ci(d) if len(d) >= 2 else (float("nan"), float("nan"))
    return {"mean": float(d.mean()) if len(d) else float("nan"), "ci": ci,
            "days": len(d), "days_above_0": int((d > 0).sum())}  # fmt: skip
