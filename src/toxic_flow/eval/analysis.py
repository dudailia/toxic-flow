"""The pre-registered analysis of a results table (PREREGISTRATION.md sections 7 to 10).

Input: metrics rows as written by engine.run (one per day, strategy and cell), possibly
from several results directories. Strategies are told apart by the label column, so each
label must have one parameter set per cell; the analysis compares settings, it does not
choose them. Output: plain dicts, and summary() for results/summary.json and the paper.
"""

import numpy as np
import polars as pl

from toxic_flow.engine.grid import QUEUE_MODELS
from toxic_flow.eval.bootstrap import (
    bootstrap_ci,
    conclusion,
    mde,
    paired_differences,
    selectivity,
    t_interval,
)

PRIMARY = ("risk_averse", "high")  # section 3
CELLS = [(q, lat) for q in QUEUE_MODELS for lat in ("low", "high")]
EXPLORATORY = {"H2": ("B3", "B2"), "H3": ("B3", "B1"), "H4": ("B2b", "B1")}
HORIZONS_S = (1, 10, 60)
BEF = "break_even_fee_bps"
SELECTIVITY_TEXT = (
    " B3 traded less than half as much notional as B2b on the median test day, so any "
    "effect is labelled as selectivity rather than better pricing."
)


def _labelled(m: pl.DataFrame) -> pl.DataFrame:
    return m if "label" in m.columns else m.with_columns(label=pl.col("strategy"))


def _rows(m: pl.DataFrame, label: str, queue: str, latency: str) -> pl.DataFrame:
    r = _labelled(m).filter(
        (pl.col("label") == label) & (pl.col("queue") == queue) & (pl.col("latency") == latency)
    )
    if r["params"].n_unique() > 1:
        raise ValueError(
            f"{label} has {r['params'].n_unique()} parameter sets in {queue}/{latency}"
        )
    return r


def _by_day(m, label, queue, latency, col) -> dict:
    r = _rows(m, label, queue, latency).unique(subset=["day", col, "fills"], keep="first")
    # Two results directories can hold the same cell; identical rows are one run reproduced.
    if r["day"].n_unique() < r.height:
        raise ValueError(f"{label} in {queue}/{latency} has a day twice with different values")
    return {d: (v, f) for d, v, f in zip(r["day"], r[col], r["fills"], strict=True)}


def compare(m, a: str, b: str, queue: str = PRIMARY[0], latency: str = PRIMARY[1], col=BEF):
    """D_i = a - b per day in one cell (section 8): mean, bootstrap and t intervals,
    days dropped for zero fills, days with D > 0, and D per day."""
    va, vb = _by_day(m, a, queue, latency, col), _by_day(m, b, queue, latency, col)
    if set(va) != set(vb):
        # Section 8 drops only zero-fill days; a day one side lacks is a missing run.
        raise ValueError(f"days differ between {a} and {b} in {queue}/{latency}: "
                         f"{sorted(set(va) ^ set(vb))}")  # fmt: skip
    days, d, dropped = paired_differences(va, vb)
    enough = len(d) >= 2
    nan2 = (float("nan"), float("nan"))
    return {
        "a": a, "b": b, "queue": queue, "latency": latency, "metric": col,
        "n": len(d), "dropped": dropped,
        "mean": float(d.mean()) if len(d) else float("nan"),
        "bootstrap_ci": bootstrap_ci(d) if enough else nan2,
        "t_ci": t_interval(d) if enough else nan2,
        "n_positive": int((d > 0).sum()),
        "per_day": dict(zip(days, d.tolist(), strict=True)),
    }  # fmt: skip


def _markouts(m, a, b) -> dict:
    """Markout differences at each horizon: day means of fills, then the day-level
    bootstrap (section 8). Exploratory."""
    return {f"markout_{h}s": compare(m, a, b, col=f"mean_markout_{h}s_bps") for h in HORIZONS_S}


def h1(m: pl.DataFrame, mde_bp: float) -> dict:
    """H1, B3 against B2b: the primary cell, the sign in all 8 cells, the section 11
    statement and the selectivity check."""
    primary = compare(m, "B3", "B2b")
    cells = {f"{q}/{lat}": compare(m, "B3", "B2b", q, lat) for q, lat in CELLS}
    empty = [c for c, r in cells.items() if r["n"] == 0]
    if empty:
        raise ValueError(f"no paired days for B3 and B2b in {empty}: every cell must be present")
    cell_means = {c: r["mean"] for c, r in cells.items()}
    out = conclusion(
        primary["bootstrap_ci"], primary["t_ci"], primary["mean"], list(cell_means.values()), mde_bp
    )
    q, lat = PRIMARY
    n3, n2 = (
        _by_day(m, "B3", q, lat, "traded_notional"),
        _by_day(m, "B2b", q, lat, "traded_notional"),
    )
    # Every test day, including those dropped from D because B3 did not trade: those are
    # the most selective days (section 8, "on the median test day").
    days = sorted(d for d in n3 if n2[d][0] > 0)
    sel = selectivity([n3[d][0] for d in days], [n2[d][0] for d in days])
    if sel["flag"]:
        out["statement"] += SELECTIVITY_TEXT
    markouts = {k: {**v, "label": "exploratory"} for k, v in _markouts(m, "B3", "B2b").items()}
    return {**out, "primary": primary, "cell_means": cell_means, "selectivity": sel,
            "markouts": markouts}  # fmt: skip


def exploratory(m: pl.DataFrame) -> dict:
    """H2 to H4 in the primary cell, with markout differences, labelled exploratory."""
    return {
        h: {"label": "exploratory", "pair": [a, b], "bef": compare(m, a, b), **_markouts(m, a, b)}
        for h, (a, b) in EXPLORATORY.items()
    }


def _has(m, label, queue=PRIMARY[0], latency=PRIMARY[1]) -> bool:
    return _rows(m, label, queue, latency).height > 0


def _contains_zero(ci) -> bool | None:
    """None without an interval (fewer than two paired days): no verdict either way."""
    if not np.all(np.isfinite(ci)):
        return None
    return bool(ci[0] <= 0 <= ci[1])


def canaries(m: pl.DataFrame, mde_bp: float) -> dict:
    """Section 10, in the primary cell. Pass rules use the bootstrap interval, the primary
    interval of section 8; the t interval is reported beside it."""
    out, text = {}, []
    if _has(m, "C1"):
        c = compare(m, "C1", "B1")
        out["C1"] = {**c, "pass": _contains_zero(c["bootstrap_ci"])}
        if _has(m, "B3"):
            # Q28: the pass rule is C1 against B1 (section 10); C1 against B3 isolates the
            # sign information and is reported beside it, as descriptive.
            out["C1"]["vs_B3"] = {**compare(m, "C1", "B3"), "label": "descriptive"}
        if out["C1"]["pass"] is None:
            text.append("C1, shuffled signs: no interval, so no verdict.")
        elif out["C1"]["pass"]:
            text.append("C1, shuffled signs, did not differ detectably from B1.")
        else:
            text.append(
                "The signal's gain does not depend on event signs, so it is not order-flow "
                "information. Primary result reported but not interpreted."
            )
    if _has(m, "C2"):
        c = compare(m, "C2", "B1")
        out["C2"] = {**c, "threshold_bp": 3 * mde_bp, "pass": c["mean"] > 3 * mde_bp}
        text.append(
            f"C2, the oracle, beat B1 by {c['mean']:.2f} bp, more than 3 times the MDE."
            if out["C2"]["pass"]
            else "C2, the oracle, did not beat B1 by 3 times the MDE: the harness cannot convert "
            "information into PnL, and the study stops."
        )
    q = PRIMARY[0]
    if _has(m, "B3", q, "zero"):
        # B3 at zero latency against B3 at each non-zero latency in the same queue model.
        mean = {
            lat: float(np.nanmean(_rows(m, "B3", q, lat).filter(pl.col("fills") > 0)[BEF]))
            for lat in ("zero", "low", "high")
            if _has(m, "B3", q, lat)
        }
        others = [v for lat, v in mean.items() if lat != "zero"]
        # A NaN mean (no day with fills) compares False with anything, so it would read as
        # "zero latency was above"; without both means there is no verdict (review, M2/M3).
        known = np.isfinite(mean["zero"]) and others and np.all(np.isfinite(others))
        flag = any(v > mean["zero"] for v in others) if known else None
        out["C3"] = {"mean_bef_bp": mean, "flag": flag}
        text.append(
            "C3, zero latency: a mean is missing (no day with fills), so no verdict."
            if flag is None
            else "Flag: B3 at a non-zero latency beat its zero-latency run on the mean."
            if flag
            else "C3, zero latency, was above B3 at every non-zero latency on the mean."
        )
    variants = sorted(
        x for x in set(_labelled(m)["label"]) if x.startswith("C4") and _has(m, x)
    )  # fmt: skip
    if variants:
        res = {v: compare(m, v, "B3") for v in variants}
        matches = {v: _contains_zero(r["bootstrap_ci"]) for v, r in res.items()}
        known = [v for v in matches.values() if v is not None]
        out["C4"] = {
            **res,
            "matches_b3": matches,
            "decay_not_driver": any(known) if known else None,
        }
        word = {True: "matched B3 within the interval", False: "differed from B3",
                None: "has no interval"}  # fmt: skip
        text.append("; ".join(f"{v} {word[x]}" for v, x in matches.items()) + ".")
        if out["C4"]["decay_not_driver"]:
            text.append("So the fitted decay is not what drives any gain.")
    out["statement"] = " ".join(text)
    return out


def mde_inputs(train: pl.DataFrame, val: pl.DataFrame, n_test: int = 16) -> dict:
    """Section 9: s is the larger of the standard deviations of D_i = BEF_B3 - BEF_B2b
    on training and on validation days, with the selected settings."""
    sd = {
        name: float(np.std(list(compare(m, "B3", "B2b")["per_day"].values()), ddof=1))
        for name, m in (("train", train), ("val", val))
    }
    if not all(np.isfinite(list(sd.values()))):
        raise ValueError(f"s needs both estimates (train and val), got {sd}")
    s = max(sd.values())
    return {"s_train_bp": sd["train"], "s_val_bp": sd["val"], "s_bp": s,
            "mde_bp": mde(s, n_test), "n_test": n_test}  # fmt: skip


def summary(m: pl.DataFrame, mde_in: dict, meta: dict) -> dict:
    """Everything the paper prints, from the confirmatory results. The MDE is recomputed
    with the same s for the number of test days present (section 9)."""
    n_test = int(_labelled(m)["day"].n_unique())
    mde_bp = mde(mde_in["s_bp"], n_test)
    h = h1(m, mde_bp)
    c = canaries(m, mde_bp)
    p = h["primary"]
    if c.get("C1", {}).get("pass") is False:
        # Section 11: when C1 fails, the primary result is reported but not interpreted.
        lo, hi = p["bootstrap_ci"]
        h["statement"] = (
            f"Mean difference {p['mean']:.2f} bp, interval [{lo:.2f}, {hi:.2f}]. The signal's "
            "gain does not depend on event signs, so it is not order-flow information. "
            "Primary result reported but not interpreted."
        )
    return {
        "h1_statement": h["statement"],
        "h1_mean_bp": p["mean"],
        "h1_ci_low_bp": p["bootstrap_ci"][0],
        "h1_ci_high_bp": p["bootstrap_ci"][1],
        "h1_t_low_bp": p["t_ci"][0],
        "h1_t_high_bp": p["t_ci"][1],
        "mde_bp": mde_bp,
        "s_bp": mde_in["s_bp"],
        "canary_statement": c["statement"],
        "n_test_days": n_test,
        "n_train_days": meta["n_train_days"],
        "n_val_days": meta["n_val_days"],
        "hftbacktest_version": meta["hftbacktest"],
        "prereg_tagged_at": meta["prereg_tagged_at"],
        "h1": h,
        "exploratory": exploratory(m),
        "canaries": c,
    }


def confirmatory_problem(metas: list[dict], m: pl.DataFrame, test_days: list[str]):
    """Why these runs may not write results/summary.json, or None if they may. Every run
    comes from configs/runs/confirmatory.yaml and is not smoke, and every label has every
    non-excluded test day in every cell it runs in. The caller checks s, the config hash
    and the commit against the tag."""
    for meta in metas:
        if meta.get("label") == "smoke":
            return "a smoke run is never the confirmatory result"
        if meta.get("config") != "configs/runs/confirmatory.yaml":
            return f"{meta.get('config')} is not configs/runs/confirmatory.yaml"
    want = set(test_days)
    if set(m["day"]) != want:
        return f"the runs cover {m['day'].n_unique()} days, not the {len(want)} test days"
    for (label, q, lat), g in _labelled(m).group_by(["label", "queue", "latency"]):
        if set(g["day"]) != want:
            return f"{label} in {q}/{lat} lacks {sorted(want - set(g['day']))}"
    return None
