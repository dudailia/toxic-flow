"""Study run configs, built from the training constants and configs/selected.yaml.

The constants come from scripts/fit_signals.py (docs/signals/train_constants.json); a
smoke file is refused. configs/selected.yaml is written by hand once Ilia approves a
selection table; the format these builders read, one entry per strategy:

    B0:  {h: 2}
    B1:  {gamma: 0.1, window_s: 300, update_every: 50}
    B2:  {c: 0.5, d: 1.0, ofi_window_s: 30.0}
    B2b: {c: 1.0, d: 0.0, tau_s: 1.0}
    B3:  {c: 0.5, d: 0.5}

K and the Hawkes parameters are filled in from the constants, so a config carries every
number its runs use.
"""

from itertools import product

C_GRID = D_GRID = (0.0, 0.5, 1.0)  # section 4
OFI_WINDOWS_S = TAUS_S = (1.0, 5.0, 30.0)
B0_H = (1, 2, 3, 5)
C4_FACTORS = (10.0, 0.1)
PRIMARY = ["risk_averse", "high"]
COMMON = {
    "quote_start": "00:30:00",  # section 3, day structure
    "quote_end": "23:59:00",
    "step_ns": 100_000_000,
    "max_lots": 10,  # inventory cap Q, section 3
    # The third level is the LPP Tier 1 maker fee, as in the smoke runs; Q6 is open.
    "fee_levels_bps": {"standard_maker": "venue", "zero": 0.0, "lp_tier1": -0.1},
}
ALL_QUEUES = ["risk_averse", "power3", "power2", "log"]


def _check(constants: dict) -> None:
    if constants.get("label") != "train":
        raise ValueError(
            f"constants labelled {constants.get('label')!r}: a smoke fit makes no study config"
        )


def _b1(selected: dict) -> dict:
    return {"gamma": selected["B1"]["gamma"], "window_s": selected["B1"]["window_s"],
            "update_every": selected["B1"].get("update_every", 50)}  # fmt: skip


def _overlay(name: str, b1: dict, c: float, d: float, constants: dict, **signal) -> dict:
    """One overlay entry with its K. C1 and C4 are B3 entries with a different name."""
    s = {"name": name, **b1, "c": c, "d": d, **signal}
    if name == "B2":
        s["K"] = constants["K"][f"B2_ofi_{signal['ofi_window_s']:g}s"]
    elif name == "B2b":
        s["K"] = constants["K"][f"B2b_ewma_{signal['tau_s']:g}s"]
    else:
        # C4 keeps B3's K (Q25 is open).
        s |= {"K": constants["K"]["B3_hawkes"], **constants["hawkes"]["params"]}
    return s


def _selected_overlay(name: str, constants: dict, selected: dict, **extra) -> dict:
    base = "B3" if name in ("C1", "C4") else name
    p = {k: v for k, v in selected[base].items() if k not in ("c", "d")}
    return _overlay(
        name, _b1(selected), selected[base]["c"], selected[base]["d"], constants, **p, **extra
    )


def _config(name: str, days, strategies, queues, latencies) -> dict:
    return {"name": name, "label": name, "days": list(days), "strategies": strategies,
            "queue_models": queues, "latencies": latencies, **COMMON}  # fmt: skip


def training(gammas, windows_s, days) -> dict:
    """M2: B0 over its h grid and B1 over Ilia's gamma and window grid (Q23), 8 cells."""
    strategies = [{"name": "B0", "h": h} for h in B0_H] + [
        {"name": "B1", "gamma": g, "window_s": w, "update_every": 50}
        for g, w in product(gammas, windows_s)
    ]
    return _config("train_b0_b1", days, strategies, ALL_QUEUES, ["low", "high"])


def tuning(constants: dict, selected: dict, days) -> dict:
    """M4: the overlay grid of section 4 on validation days in the primary cell."""
    _check(constants)
    b1 = _b1(selected)
    s = [_overlay("B2", b1, c, d, constants, ofi_window_s=w)
         for c, d, w in product(C_GRID, D_GRID, OFI_WINDOWS_S)]  # fmt: skip
    s += [_overlay("B2b", b1, c, d, constants, tau_s=t)
          for c, d, t in product(C_GRID, D_GRID, TAUS_S)]  # fmt: skip
    s += [_overlay("B3", b1, c, d, constants) for c, d in product(C_GRID, D_GRID)]
    return _config("tune_val", days, s, [PRIMARY[0]], [PRIMARY[1]])


def _canary_entries(constants: dict, selected: dict, cells=None) -> list[dict]:
    """C1, C2, C4 at x10 and x0.1, and C3 as B3 at zero latency (section 10)."""
    where = {"cells": [PRIMARY]} if cells else {}
    s = [
        _selected_overlay("C1", constants, selected, seed=1729) | where,
        {"name": "C2", **_b1(selected)} | where,
        *(_selected_overlay("C4", constants, selected, label=f"C4_x{f:g}", decay_factor=f) | where
          for f in C4_FACTORS),
    ]  # fmt: skip
    return s + [_selected_overlay("B3", constants, selected) | {"cells": [[PRIMARY[0], "zero"]]}]


def canaries(constants: dict, selected: dict, days) -> dict:
    """M4: canaries on validation days, with B1, B2b and B3 at the selected settings, so
    this one run gives the canary comparisons and the validation estimate of s."""
    _check(constants)
    s = [{"name": "B1", **_b1(selected)}]
    s += [_selected_overlay(n, constants, selected) for n in ("B2b", "B3")]
    return _config(
        "canaries_val", days, s + _canary_entries(constants, selected), [PRIMARY[0]], [PRIMARY[1]]
    )


def mde_train(constants: dict, selected: dict, days) -> dict:
    """M4: B3 and B2b at the selected settings on training days, for s (section 9)."""
    _check(constants)
    s = [_selected_overlay(n, constants, selected) for n in ("B2b", "B3")]
    return _config("mde_train", days, s, [PRIMARY[0]], [PRIMARY[1]])


def confirmatory(constants: dict, selected: dict, days) -> dict:
    """M5: one grid. B0 to B3 in all 8 cells; canaries in the primary cell; C3 at zero."""
    _check(constants)
    s = [{"name": "B0", "h": selected["B0"]["h"]}, {"name": "B1", **_b1(selected)}]
    s += [_selected_overlay(n, constants, selected) for n in ("B2", "B2b", "B3")]
    s += _canary_entries(constants, selected, cells=True)
    return _config("confirmatory", days, s, ALL_QUEUES, ["low", "high"])
