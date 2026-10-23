"""Parameter selection by the pre-registered rule (PREREGISTRATION.md section 4).

B0 and B1 on training days, overlays on validation days, both in the primary cell: the
candidate with the highest mean daily break-even fee wins. Overlay ties go to the smaller
c + d, then the shorter OFI window or EWMA decay. This module ranks and reports; it never
writes configs/selected.yaml, which needs Ilia's approval (SPEC.md AC2.5 and AC4.1).
Where section 4 gives no rule, it raises instead of inventing one.
"""

import json

import polars as pl

PRIMARY = ("risk_averse", "high")  # section 3
# Candidates with c = d = 0 reduce to B1 and tie exactly; this absorbs only rounding.
TIE_BP = 1e-9
SIGNAL_SCALE = ("ofi_window_s", "tau_s")  # B2's window W, B2b's decay; B3 has neither


def candidate_table(metrics: pl.DataFrame, strategy: str, days: list[str]) -> pl.DataFrame:
    """One row per candidate (params JSON) in the primary cell over the given days: mean
    daily BEF, days counted, days with zero fills. Every candidate must have every day."""
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
            mean_bef_bps=pl.col("break_even_fee_bps").mean(),
            n_days=pl.col("day").n_unique(),
            zero_fill_days=(pl.col("fills") == 0).sum(),
        )
        .sort("params")
    )
    short = t.filter(pl.col("n_days") < len(days))
    if short.height:
        raise ValueError(
            f"{short.height} candidate(s) missing days of {len(days)}: {short['params'].to_list()}"
        )
    return t


def _tie_key(params: dict) -> tuple:
    return (params["c"] + params["d"], next((params[k] for k in SIGNAL_SCALE if k in params), 0.0))


def select(table: pl.DataFrame, strategy: str) -> dict:
    """The winning candidate, its mean daily BEF and how many candidates tied at the top."""
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
