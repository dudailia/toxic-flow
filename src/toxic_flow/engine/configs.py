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
# B1 grid (section 4): factors of two around the GLFT tutorial's gamma 0.05 and 10-minute
# window; every window fits inside the 30-minute warm-up.
B1_GAMMAS = (0.025, 0.05, 0.1, 0.2)
B1_WINDOWS_S = (300, 600, 1200)
# Section 4 grid-edge rule (Q41): every first choice sat at the top edge, so each grid gets
# two more steps upward, in its own spacing (h continues 1, 2, 3, 5; gamma and window
# double). Windows of 40 and 80 min exceed the warm-up, so those candidates quote later.
B0_H_EXT = (8, 13)
B1_GAMMAS_EXT = (0.4, 0.8)
B1_WINDOWS_S_EXT = (2400, 4800)
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


def _signal_key(name: str, signal: dict) -> str:
    """The training-constant key of a signal setting. C1 is B3 on shuffled sides, so it
    uses B3's constants; C4 has its own, since its decay is a different parameter setting
    (Q25, decided 2026-10-23)."""
    if name == "B2":
        return f"B2_ofi_{signal['ofi_window_s']:g}s"
    if name == "B2b":
        return f"B2b_ewma_{signal['tau_s']:g}s"
    return f"C4_x{signal['decay_factor']:g}" if name == "C4" else "B3_hawkes"


def _overlay(name: str, b1: dict, c: float, d: float, constants: dict, **signal) -> dict:
    """One overlay entry with its K. C1 and C4 are B3 entries with a different name."""
    s = {
        "name": name,
        **b1,
        "c": c,
        "d": d,
        **signal,
        "K": constants["K"][_signal_key(name, signal)],
    }
    if name not in ("B2", "B2b"):
        s |= constants["hawkes"]["params"]
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


def training(days) -> dict:
    """M2 selection: B0 over its h grid and B1 over its gamma and window grid (section 4),
    on training days in the primary cell."""
    strategies = [{"name": "B0", "h": h} for h in B0_H] + [
        {"name": "B1", "gamma": g, "window_s": w, "update_every": 50}
        for g, w in product(B1_GAMMAS, B1_WINDOWS_S)
    ]
    return _config("train_select", days, strategies, [PRIMARY[0]], [PRIMARY[1]])


def training_extended(days) -> dict:
    """M2, section 4 grid-edge rule: the new B0 values and every B1 pair in the extended
    product that the first selection run did not have, on training days in the primary
    cell. The selection then reads both runs."""
    gammas, windows = B1_GAMMAS + B1_GAMMAS_EXT, B1_WINDOWS_S + B1_WINDOWS_S_EXT
    strategies = [{"name": "B0", "h": h} for h in B0_H_EXT] + [
        {"name": "B1", "gamma": g, "window_s": w, "update_every": 50}
        for g, w in product(gammas, windows)
        if g in B1_GAMMAS_EXT or w in B1_WINDOWS_S_EXT
    ]
    return _config("train_select_ext", days, strategies, [PRIMARY[0]], [PRIMARY[1]])


# Q45: the latest first quote among the candidates. The 80-minute window is full at step
# 47,999 and the fit runs every 50 steps, so the first quote is at 4,800 s, 01:20:00.
SELECT_FROM = "01:20:00"


def training_window(days) -> dict:
    """M2 selection with the grid-edge extension and one scoring window (section 4, Q41
    and Q45): every B0 and B1 candidate, old and new, on training days in the primary cell,
    with sel_* metrics from SELECT_FROM to the end of quoting beside the full-day ones."""
    gammas, windows = B1_GAMMAS + B1_GAMMAS_EXT, B1_WINDOWS_S + B1_WINDOWS_S_EXT
    strategies = [{"name": "B0", "h": h} for h in B0_H + B0_H_EXT] + [
        {"name": "B1", "gamma": g, "window_s": w, "update_every": 50}
        for g, w in product(gammas, windows)
    ]
    cfg = _config("train_select_window", days, strategies, [PRIMARY[0]], [PRIMARY[1]])
    return cfg | {"select_from": SELECT_FROM}


def training_chosen(selected: dict, days) -> dict:
    """M2: the chosen B0 and B1 on training days in all 8 cells (AC2.1, AC2.4)."""
    s = [{"name": "B0", "h": selected["B0"]["h"]}, {"name": "B1", **_b1(selected)}]
    return _config("train_chosen", days, s, ALL_QUEUES, ["low", "high"])


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
    if selected["B3"]["c"] > 0:
        # Descriptive, not a section 10 canary (leakage audit A1, Q44): with c > 0, C1's
        # random u moves the quote centre, so C1 can lose to B1 from that noise alone. B3
        # and C1 with c = 0 at the selected d measure how much of C1's gap that explains.
        b1, d = _b1(selected), selected["B3"]["d"]
        s += [_overlay("B3", b1, 0.0, d, constants, label="B3_c0"),
              _overlay("C1", b1, 0.0, d, constants, label="C1_c0", seed=1729)]  # fmt: skip
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


# v2 (PREREGISTRATION.md section 4, Design history): B0 and B1 join the touch and have no
# parameters; the overlay steps back on the toxic side.
V2_P = (0.05, 0.10, 0.25, 0.50)  # pull rate: share of training-day steps with |u| > theta_u
V2_K_TICKS = (1, 5, "pull")
V2_MAGNITUDE = (False, True)


def v2_training(days) -> dict:
    """v2 B0 and B1 on training days in all 8 cells (reported; nothing is chosen)."""
    s = [{"name": "B0", "design": "v2"}, {"name": "B1", "design": "v2"}]
    return _config("v2_train", days, s, ALL_QUEUES, ["low", "high"])


def _v2_overlay(name, constants, thresholds, p, k_ticks, magnitude, **signal) -> dict:
    """One v2 overlay entry with every number its run uses: K, and theta_u at pull rate p
    and theta_m from the training days (section 5) for its signal setting."""
    key = _signal_key(name, signal)
    th = thresholds["signals"][key]
    s = {"name": name, "design": "v2", "p": p, "k_ticks": k_ticks, "magnitude": magnitude,
         **signal, "K": constants["K"][key], "theta_u": th["theta_u"][f"{p:g}"],
         "theta_m": th["theta_m"]}  # fmt: skip
    if name not in ("B2", "B2b"):
        s |= constants["hawkes"]["params"]
    return s


def _check_thresholds(thresholds: dict) -> None:
    if thresholds.get("label") != "train":
        raise ValueError(f"thresholds labelled {thresholds.get('label')!r}, not train")


def v2_tuning(constants: dict, thresholds: dict, days, name="v2_tune_val") -> dict:
    """v2 M4: the overlay grid of section 4 on validation days in the primary cell, 24
    settings per signal setting: B2 72, B2b 72, B3 24."""
    _check(constants)
    _check_thresholds(thresholds)
    grid = list(product(V2_P, V2_K_TICKS, V2_MAGNITUDE))
    s = [_v2_overlay("B2", constants, thresholds, p, k, mg, ofi_window_s=w)
         for w in OFI_WINDOWS_S for p, k, mg in grid]  # fmt: skip
    s += [_v2_overlay("B2b", constants, thresholds, p, k, mg, tau_s=t)
          for t in TAUS_S for p, k, mg in grid]  # fmt: skip
    s += [_v2_overlay("B3", constants, thresholds, p, k, mg) for p, k, mg in grid]
    return _config(name, days, s, [PRIMARY[0]], [PRIMARY[1]])


def _v2_selected(name, constants, thresholds, selected, **extra) -> dict:
    base = "B3" if name in ("C1", "C4") else name
    sel = selected[base]
    signal = {k: v for k, v in sel.items() if k not in ("p", "k_ticks", "magnitude")}
    return _v2_overlay(name, constants, thresholds, sel["p"], sel["k_ticks"], sel["magnitude"],
                       **signal, **extra)  # fmt: skip


def v2_canaries(constants: dict, thresholds: dict, selected: dict, days) -> dict:
    """v2 M4 on validation days, primary cell: B1, B2b and B3 at the selected settings (the
    validation estimate of s), and the canaries of section 10: C1 (B3's settings and
    thresholds on shuffled sides), C2 (the oracle), C4 at x10 and x0.1 (own K and
    thresholds), C3 (B3 at zero latency)."""
    _check(constants)
    _check_thresholds(thresholds)
    sel = lambda n, **e: _v2_selected(n, constants, thresholds, selected, **e)  # noqa: E731
    s = [{"name": "B1", "design": "v2"}, sel("B2b"), sel("B3"), sel("C1", seed=1729),
         {"name": "C2", "design": "v2"},
         *(sel("C4", label=f"C4_x{f:g}", decay_factor=f) for f in C4_FACTORS),
         sel("B3") | {"cells": [[PRIMARY[0], "zero"]]}]  # fmt: skip
    return _config("v2_canaries_val", days, s, [PRIMARY[0]], [PRIMARY[1]])


def v2_mde_train(constants: dict, thresholds: dict, selected: dict, days) -> dict:
    """v2 M4: B3 and B2b at the selected settings on training days, for s (section 9)."""
    _check(constants)
    _check_thresholds(thresholds)
    s = [_v2_selected(n, constants, thresholds, selected) for n in ("B2b", "B3")]
    return _config("v2_mde_train", days, s, [PRIMARY[0]], [PRIMARY[1]])


# Random-pull controls (Q53, decided 2026-10-26; PREREGISTRATION.md section 10): B1 that
# pulls a random side at another strategy's realised pull rate on each day. R1 is C1's
# control (the C1 pass rule); R_B3 and R_B2b are exploratory. Three seeds each.
R_SEEDS = (1, 2, 3)


def quote_hours(cfg: dict = COMMON) -> float:
    """Length of the quoting window in hours, from quote_start and quote_end."""

    def hours(hms: str) -> float:
        h, m, s = (int(x) for x in hms.split(":"))
        return h + m / 60 + s / 3600

    return hours(cfg["quote_end"]) - hours(cfg["quote_start"])


def _random_pulls(of: str, rates: dict, label: str, k_ticks) -> list[dict]:
    return [{"name": "R", "design": "v2", "label": f"{label}_s{seed}", "rate_of": of,
             "k_ticks": k_ticks, "seed": seed, "pull_rate": dict(rates)}
            for seed in R_SEEDS]  # fmt: skip


def v2_random_pulls(constants: dict, thresholds: dict, selected: dict, rates: dict, days) -> dict:
    """v2 M4 on validation days, primary cell: R1 (C1's rate) and the exploratory R_B3 and
    R_B2b (B3's and B2b's rates), with B1, C1, B3 and B2b at the selected settings in the
    same run, so each comparison is within one run. rates maps C1, B3 and B2b to {day:
    realised toxic share} from the canary run. K is pull for every R, as for C1, B3 and B2b
    at the selected settings."""
    _check(constants)
    _check_thresholds(thresholds)
    sel = lambda n, **e: _v2_selected(n, constants, thresholds, selected, **e)  # noqa: E731
    s = [{"name": "B1", "design": "v2"}, sel("C1", seed=1729), sel("B3"), sel("B2b")]
    return _config("v2_random_pulls_val", days, s + _controls(selected, rates, days),
                   [PRIMARY[0]], [PRIMARY[1]])  # fmt: skip


def _controls(selected: dict, rates: dict, days) -> list[dict]:
    """R1, R_B3 and R_B2b with three seeds each, at the per-day rates given, each stepping
    back by the K of the strategy it controls for (C1 has B3's settings). The magnitude
    rule is off in R, so the strategies must have it off too."""
    if sorted(rates) != ["B2b", "B3", "C1"]:
        raise ValueError(f"rates for {sorted(rates)}, not C1, B3 and B2b")
    if any(sorted(r) != sorted(days) for r in rates.values()):
        raise ValueError("rates do not cover exactly the run's days")
    for name in ("B2b", "B3"):
        if selected[name]["magnitude"]:
            raise ValueError(f"{name} uses the magnitude rule, which R does not have")
    k3, k2 = selected["B3"]["k_ticks"], selected["B2b"]["k_ticks"]
    return [*_random_pulls("C1", rates["C1"], "R1", k3),
            *_random_pulls("B3", rates["B3"], "R_B3", k3),
            *_random_pulls("B2b", rates["B2b"], "R_B2b", k2)]  # fmt: skip


# Run-length controls (exploratory, Ilia 2026-10-26; sections 7 and 10): R pulls each
# step independently, so it starts many more pulled runs than B3 or B2b, and each run gives
# up the queue place. RL matches each day's number of runs as well as the rate.
def _run_length_controls(selected: dict, rates: dict, episodes: dict, days) -> list[dict]:
    """RL_B3 and RL_B2b with three seeds each, at B3's and B2b's per-day pull rates and
    numbers of pulled runs, each stepping back by its strategy's K."""
    if sorted(episodes) != ["B2b", "B3"]:
        raise ValueError(f"pulled runs for {sorted(episodes)}, not B3 and B2b")
    for name in ("B2b", "B3"):
        if sorted(rates[name]) != sorted(days) or sorted(episodes[name]) != sorted(days):
            raise ValueError(f"{name}: rates or pulled runs do not cover exactly the run's days")
        if selected[name]["magnitude"]:
            raise ValueError(f"{name} uses the magnitude rule, which RL does not have")
    return [{"name": "RL", "design": "v2", "label": f"RL_{of}_s{seed}", "rate_of": of,
             "k_ticks": selected[of]["k_ticks"], "seed": seed, "pull_rate": dict(rates[of]),
             "episodes": {d: int(n) for d, n in episodes[of].items()}}
            for of in ("B3", "B2b") for seed in R_SEEDS]  # fmt: skip


def v2_run_length(constants: dict, thresholds: dict, selected: dict, rates: dict,
                  episodes: dict, days) -> dict:  # fmt: skip
    """v2 M4 on validation days, primary cell, exploratory: RL_B3 and RL_B2b with B1, B3
    and B2b at the selected settings in the same run. rates and episodes map B3 and B2b to
    {day: realised toxic share} and {day: toxic episodes} from a committed run."""
    _check(constants)
    _check_thresholds(thresholds)
    sel = lambda n: _v2_selected(n, constants, thresholds, selected)  # noqa: E731
    s = [{"name": "B1", "design": "v2"}, sel("B3"), sel("B2b")]
    return _config("v2_run_length_val", days,
                   s + _run_length_controls(selected, rates, episodes, days),
                   [PRIMARY[0]], [PRIMARY[1]])  # fmt: skip


def v2_confirmatory(constants: dict, thresholds: dict, selected: dict, days) -> dict:
    """v2 M5, first of the two planned test-day runs: B0 to B3 in all 8 cells; C1, C2 and
    C4 in the primary cell; C3 (B3 at zero latency) in the risk-averse model. Its realised
    toxic shares of C1, B3 and B2b are the rates of the second run (section 10)."""
    _check(constants)
    _check_thresholds(thresholds)
    sel = lambda n, **e: _v2_selected(n, constants, thresholds, selected, **e)  # noqa: E731
    where = {"cells": [PRIMARY]}
    s = [{"name": "B0", "design": "v2"}, {"name": "B1", "design": "v2"},
         sel("B2"), sel("B2b"), sel("B3"),
         sel("C1", seed=1729) | where, {"name": "C2", "design": "v2"} | where,
         *(sel("C4", label=f"C4_x{f:g}", decay_factor=f) | where for f in C4_FACTORS),
         sel("B3") | {"cells": [[PRIMARY[0], "zero"]]}]  # fmt: skip
    return _config("confirmatory", days, s, ALL_QUEUES, ["low", "high"])


def v2_confirmatory_controls(selected: dict, rates: dict, episodes: dict, days) -> dict:
    """v2 M5, second planned test-day run: R1, R_B3 and R_B2b in the primary cell at the
    realised toxic shares of C1, B3 and B2b in the first run, day by day, and RL_B3 and
    RL_B2b at B3's and B2b's shares and numbers of pulled runs."""
    s = _controls(selected, rates, days) + _run_length_controls(selected, rates, episodes, days)
    return _config("confirmatory_controls", days, s, [PRIMARY[0]], [PRIMARY[1]])
