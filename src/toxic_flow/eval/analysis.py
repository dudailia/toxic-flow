"""The pre-registered analysis of a results table (PREREGISTRATION.md sections 7 to 10).

Input: metrics rows as written by engine.run (one per day, strategy and cell), possibly
from several results directories. Strategies are told apart by the label column, so each
label must have one parameter set per cell; the analysis compares settings, it does not
choose them. Output: plain dicts, and summary() for results/summary.json and the paper.
"""

import json
import re

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


SEED_LABEL = re.compile(r"^(R.*)_s\d+$")


def with_seed_means(m: pl.DataFrame) -> pl.DataFrame:
    """Adds, for each random-pull control run with several seeds (labels such as R1_s1,
    R1_s2, R1_s3, or RL_B3_s1 for the run-length control), one row per day and cell under the bare label (R1) holding the mean over
    seeds of each metric compared. The control's day value is that mean, so the seeds
    average out the random draw before the day-level bootstrap."""
    m = _labelled(m)
    seeded = m.with_columns(base=pl.col("label").str.extract(SEED_LABEL.pattern, 1)).filter(
        pl.col("base").is_not_null()
    )
    # Idempotent: a bare label already present was averaged by an earlier call.
    seeded = seeded.filter(~pl.col("base").is_in(m["label"].unique().to_list()))
    if seeded.is_empty():
        return m
    cols = [c for c in (BEF, "fills", "gross_pnl", "traded_notional", "toxic_share",
                        "toxic_episodes", *(f"mean_markout_{h}s_bps" for h in HORIZONS_S))
            if c in m.columns]  # fmt: skip
    means = seeded.group_by("base", "day", "queue", "latency").agg(
        pl.col(cols).mean(), seeds=pl.col("label").sort().str.join(","),
        strategy=pl.col("strategy").first(),
    )  # fmt: skip
    means = means.with_columns(
        label=pl.col("base"),
        params=pl.concat_str(pl.lit('{"seeds": "'), pl.col("seeds"), pl.lit('"}')),
    ).drop("base", "seeds")  # fmt: skip
    return pl.concat([m, means], how="diagonal_relaxed")


def canaries(m: pl.DataFrame, mde_bp: float) -> dict:
    """Section 10, in the primary cell. Pass rules use the bootstrap interval, the primary
    interval of section 8; the t interval is reported beside it."""
    out, text = {}, []
    m = with_seed_means(m)
    if _has(m, "C1") and _has(m, "R1"):
        # Q53 (decided 2026-10-26, after C1 failed against B1 on validation days): pulling
        # a side costs its queue place even without information, so C1 is judged against
        # R1, B1 pulling a random side at C1's realised rate. C1 - B1, the rule first
        # written, is reported beside it.
        c = compare(m, "C1", "R1")
        out["C1"] = {**c, "rule": "C1 - R1", "pass": _contains_zero(c["bootstrap_ci"])}
        out["C1"]["vs_B1"] = {**compare(m, "C1", "B1"), "label": "rule first written"}
    elif _has(m, "C1"):
        # Without R1 there is no verdict: the rule first written (C1 - B1) is superseded,
        # and it fails by construction when pulling costs queue place (Q53).
        c = compare(m, "C1", "B1")
        out["C1"] = {**c, "rule": "C1 - R1, R1 missing", "pass": None,
                     "vs_B1": {**c, "label": "rule first written"}}  # fmt: skip
    if "C1" in out:
        if _has(m, "B3"):
            # Q28: C1 against B3 isolates the sign information and is reported beside the
            # pass rule, as descriptive.
            out["C1"]["vs_B3"] = {**compare(m, "C1", "B3"), "label": "descriptive"}
        if out["C1"]["rule"].endswith("missing"):
            text.append("C1, shuffled signs: its control R1 did not run, so no verdict.")
        elif out["C1"]["pass"] is None:
            text.append("C1, shuffled signs: no interval, so no verdict.")
        elif out["C1"]["pass"]:
            ref = out["C1"]["rule"].split(" - ")[1]
            text.append(f"C1, shuffled signs, did not differ detectably from {ref}.")
        else:
            text.append(
                "The signal's gain does not depend on event signs, so it is not order-flow "
                "information. Primary result reported but not interpreted."
            )
    if _has(m, "C2"):
        c = compare(m, "C2", "B1")
        out["C2"] = {**c, "threshold_bp": 3 * mde_bp, "pass": c["mean"] > 3 * mde_bp}
        text.append(
            f"C2, the oracle, beat B1 by {c['mean']:.4f} bp, more than 3 times the MDE."
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
    m = with_seed_means(m)
    h = h1(m, mde_bp)
    c = canaries(m, mde_bp)
    ex = exploratory(m)
    p = h["primary"]
    if c.get("C1", {}).get("pass") is False:
        # Section 11: when C1 fails, the primary result is reported but not interpreted.
        lo, hi = p["bootstrap_ci"]
        h["statement"] = (
            f"Mean difference {p['mean']:.4f} bp, interval [{lo:.4f}, {hi:.4f}]. The signal's "
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
        "h1_days_positive": p["n_positive"],
        "h1_n_days": p["n"],
        "h1_cells_same_sign": int(
            sum(np.sign(v) == np.sign(p["mean"]) for v in h["cell_means"].values())
        ),
        "selectivity_ratio": h["selectivity"]["median_notional_ratio"],
        **{f"{k.lower()}_{x}": v for k, r in ex.items() for x, v in _flat(r["bef"]).items()},
        **_canary_keys(m, c),
        "h1": h,
        "exploratory": ex,
        "canaries": c,
    }


def _canary_keys(m: pl.DataFrame, c: dict) -> dict:
    """Flat keys for C1 against R1 (and the rule first written, against B1), C2, and the
    exploratory random-pull comparisons, for whichever of them ran."""
    out = {}
    c1 = c.get("C1", {})
    if c1.get("rule") == "C1 - R1":
        out |= {f"c1_r1_{x}": v for x, v in _flat(c1).items()}
        out |= {f"c1_b1_{x}": v for x, v in _flat(c1["vs_B1"]).items()}
    if "C2" in c:
        out["c2_b1_mean_bp"] = c["C2"]["mean"]
    # Exploratory (sections 7 and 10): each overlay against random pulls at its own rate.
    # rp_ against R (rate only), rl_ against RL (rate and number of pulled runs), f_
    # against F (no rejoining the side just filled, at B3's training-day pull rate).
    for a, r, key in (("B3", "R_B3", "rp"), ("B2b", "R_B2b", "rp"),
                      ("B3", "RL_B3", "rl"), ("B2b", "RL_B2b", "rl"), ("B3", "F", "f")):  # fmt: skip
        if _has(m, a) and _has(m, r):
            out |= {f"{key}_{a.lower()}_{x}": v for x, v in _flat(compare(m, a, r)).items()}
    return out


def _flat(c: dict) -> dict:
    """The numbers of one comparison the paper prints, as flat keys."""
    return {"mean_bp": c["mean"], "ci_low_bp": c["bootstrap_ci"][0],
            "ci_high_bp": c["bootstrap_ci"][1], "days_positive": c["n_positive"]}  # fmt: skip


CONFIRMATORY = ("configs/runs/confirmatory.yaml", "configs/runs/confirmatory_controls.yaml")


def confirmatory_problem(metas: list[dict], m: pl.DataFrame, test_days: list[str]):
    """Why these runs may not write results/summary.json, or None if they may. The runs are
    the two planned test-day runs, one of each: configs/runs/confirmatory.yaml and its
    random-pull controls, configs/runs/confirmatory_controls.yaml (section 10). None is
    smoke, every label has every non-excluded test day in every cell it runs in, and every
    control pulls at the realised toxic share of the strategy it controls for, on each day,
    in the first run (an RL control also at its number of toxic episodes). The caller checks s, the config hashes and the commits against the
    tag."""
    for meta in metas:
        if meta.get("label") == "smoke":
            return "a smoke run is never the confirmatory result"
        if meta.get("config") not in CONFIRMATORY:
            return f"{meta.get('config')} is not one of {', '.join(CONFIRMATORY)}"
    for config in CONFIRMATORY:
        n = sum(meta.get("config") == config for meta in metas)
        if n != 1:
            return f"{n} runs of {config}, not 1"
    want = set(test_days)
    if set(m["day"]) != want:
        return f"the runs cover {m['day'].n_unique()} days, not the {len(want)} test days"
    m = _labelled(m)
    for (label, q, lat), g in m.group_by(["label", "queue", "latency"]):
        if set(g["day"]) != want:
            return f"{label} in {q}/{lat} lacks {sorted(want - set(g['day']))}"
    for r in m.filter(pl.col("strategy").is_in(["R", "RL"])).iter_rows(named=True):
        p = json.loads(r["params"])
        done = _rows(m, p["rate_of"], *PRIMARY).filter(pl.col("day") == r["day"])
        if done.height != 1 or abs(done["toxic_share"][0] - p["pull_rate"][r["day"]]) > 1e-12:
            return f"{r['label']} on {r['day']} does not pull at {p['rate_of']}'s realised rate"
        if r["strategy"] == "RL" and done["toxic_episodes"][0] != p["episodes"][r["day"]]:
            return f"{r['label']} on {r['day']} is not matched to {p['rate_of']}'s pulled runs"
    return None
