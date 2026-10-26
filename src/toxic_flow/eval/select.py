"""Parameter selection by the pre-registered rule (PREREGISTRATION.md section 4).

B0 and B1 on training days, overlays on validation days, both in the primary cell: the
candidate with the highest mean daily break-even fee wins. v1 overlay ties go to the smaller
c + d, then the shorter OFI window or EWMA decay; v2 ties as in K_ORDER below. This module
ranks and reports; it never writes configs/selected.yaml, which needs Ilia's approval
(SPEC.md AC2.5 and AC4.1).
Where section 4 gives no rule, it raises instead of inventing one.
"""

import json

import polars as pl

PRIMARY = ("risk_averse", "high")  # section 3
# Candidates with c = d = 0 reduce to B1 and tie exactly; this absorbs only rounding.
TIE_BP = 1e-9
SIGNAL_SCALE = ("ofi_window_s", "tau_s")  # B2's window W, B2b's decay; B3 has neither
# Section 4 grid-edge rule (Q41): a B0 or B1 candidate whose median training day has fewer
# fills than this in the primary cell is not eligible, so a grid pushed to very wide quotes
# cannot win on a handful of fills.
MIN_MEDIAN_FILLS = 100


def candidate_table(
    metrics: pl.DataFrame, strategy: str, days: list[str], prefix: str = ""
) -> pl.DataFrame:
    """One row per candidate (params JSON) in the primary cell over the given days: mean
    daily BEF, days counted, days with zero fills, median daily fills. Every candidate must
    have every day. prefix "sel_" reads the selection-window columns (Q45)."""
    bef, fills = f"{prefix}break_even_fee_bps", f"{prefix}fills"
    queue, latency = PRIMARY
    m = metrics.filter(
        (pl.col("strategy") == strategy)
        & (pl.col("queue") == queue)
        & (pl.col("latency") == latency)
        & pl.col("day").is_in(days)
    )
    t = (
        m.group_by("params")
        .agg(
            mean_bef_bps=pl.col(bef).mean(),
            n_days=pl.col("day").n_unique(),
            zero_fill_days=(pl.col(fills) == 0).sum(),
            median_fills=pl.col(fills).median(),
        )
        .sort("params")
    )
    short = t.filter(pl.col("n_days") < len(days))
    if short.height:
        raise ValueError(
            f"{short.height} candidate(s) missing days of {len(days)}: {short['params'].to_list()}"
        )
    return t


# v2 tie order of section 4: the smaller p, then K (1 tick, 5 ticks, pull), then the
# magnitude rule off, then the shorter window or decay.
K_ORDER = {1: 0, 5: 1, "pull": 2}


def _tie_key(params: dict) -> tuple:
    scale = next((params[k] for k in SIGNAL_SCALE if k in params), 0.0)
    if params.get("design") == "v2":
        return (params["p"], K_ORDER[params["k_ticks"]], params["magnitude"], scale)
    return (params["c"] + params["d"], scale)


def select(table: pl.DataFrame, strategy: str) -> dict:
    """The winning candidate, its mean daily BEF and how many candidates tied at the top.
    For B0 and B1, candidates under MIN_MEDIAN_FILLS are dropped first."""
    if strategy in ("B0", "B1"):
        table = table.filter(eligible(table))
        if table.is_empty():
            raise ValueError(f"no {strategy} candidate has {MIN_MEDIAN_FILLS} median daily fills")
    bad = table.filter(pl.col("zero_fill_days") > 0)
    if bad.height:
        # BEF is undefined on a day without fills and section 4 says nothing about it.
        raise ValueError(f"days without fills, no rule in section 4: {bad['params'].to_list()}")
    best = table["mean_bef_bps"].max()
    top = [json.loads(p) for p in table.filter(pl.col("mean_bef_bps") >= best - TIE_BP)["params"]]
    if len(top) > 1:
        if strategy in ("B0", "B1"):
            raise ValueError(f"{len(top)}-way tie and section 4 has no tie rule for {strategy}")
        top.sort(key=_tie_key)
        if _tie_key(top[0]) == _tie_key(top[1]):
            raise ValueError(f"tie that the section 4 rule does not break: {top[:2]}")
    return {"params": top[0], "mean_bef_bps": float(best), "tied": len(top)}


def eligible(table: pl.DataFrame) -> pl.Series:
    """B0 and B1 eligibility under the section 4 grid-edge rule (Q41)."""
    return table["median_fills"] >= MIN_MEDIAN_FILLS


def at_edge(value: float, grid: tuple) -> str | None:
    """'low' or 'high' when the value is the grid's smallest or largest, else None."""
    if value == min(grid):
        return "low"
    return "high" if value == max(grid) else None
