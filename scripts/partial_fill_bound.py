#!/usr/bin/env python3
"""How often does the no-partial-fill exchange fill a whole order on a smaller print?

Usage: uv run python scripts/partial_fill_bound.py YYYY-MM-DD results/<hash> [results/<hash> ...]

docs/ENGINE.md (exchange model, Q3): NoPartialFillExchange fills an order at the front of
the queue in full on any trade at its price, whatever the trade size. For each fill of
B0, B1, B3 and C2 in the primary cell, from the first run that has them, this matches the raw
prints of the fill's exchange timestamp on the opposite aggressor side:
- through: a print beyond the order's price, so a full fill is plausible;
- at price: prints only at the order's price; overfilled when their total is below the
  order size. This is a lower bound on overfilled fills, since the queue ahead also
  takes part of the print and is not visible here;
- no print: the fill came from a book update crossing the price.
Markouts of each group show whether the overfilled fills are better than the rest,
which is the direction of the bias. Writes docs/smoke/partial_fill_bound_<day>.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from toxic_flow.data.split_lock import assert_allowed, split_of

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ("risk_averse", "high")


def prints(day: str) -> pl.DataFrame:
    raw = ROOT / "data" / "raw" / day / "trades.csv.gz"
    t = pl.read_csv(raw, columns=["timestamp", "side", "price", "amount"])
    # Tardis side is the aggressor; our buy is filled by sells and our sell by buys.
    return t.select(
        exch_ts=pl.col("timestamp") * 1000,
        aggressor=pl.when(pl.col("side") == "buy").then(1).otherwise(-1).cast(pl.Int8),
        print_px=pl.col("price"),
        amount=pl.col("amount"),
    )


def classify(fills: pl.DataFrame, p: pl.DataFrame) -> pl.DataFrame:
    """One row per fill with its group: through, at_price_overfilled, at_price, no_print."""
    f = fills.with_row_index("fill").with_columns(aggressor=-pl.col("side"))
    j = f.join(p, on=["exch_ts", "aggressor"], how="left")
    # Through: a sell print below our bid, or a buy print above our ask.
    j = j.with_columns(
        through=(pl.col("print_px") - pl.col("price")) * pl.col("side") < -1e-9,
        at=(pl.col("print_px") - pl.col("price")).abs() < 1e-9,
    )
    g = j.group_by("fill").agg(
        pl.col("through").any(),
        (pl.col("amount") * pl.col("at")).sum().alias("at_qty"),
        pl.col("print_px").is_not_null().any().alias("any_print"),
    )
    f = f.join(g, on="fill")
    group = (
        pl.when(~pl.col("any_print")).then(pl.lit("no_print"))
        .when(pl.col("through")).then(pl.lit("through"))
        .when(pl.col("at_qty") < pl.col("qty") - 1e-12).then(pl.lit("at_price_overfilled"))
        .otherwise(pl.lit("at_price"))
    )  # fmt: skip
    return f.with_columns(group=group)


def summary(f: pl.DataFrame) -> dict:
    # Upper bound: every fill made only by prints at the order's price could be overfilled.
    at = f.filter(pl.col("group").str.starts_with("at_price")).height
    out = {"fills": f.height, "at_price_upper_bound_share": round(at / f.height, 4)}
    for name, g in f.group_by("group"):
        out[name[0]] = {
            "fills": g.height,
            "share": round(g.height / f.height, 4),
            **{f"mean_markout_{h}s_bps": round(float(np.nanmean(g[f"markout_{h}s_bps"])), 4)
               for h in (1, 10, 60)},
        }  # fmt: skip
    return out


LABELS = ("B0", "B1", "B3", "C2")


def main(day: str, runs: list[Path]) -> None:
    assert_allowed(day)
    if split_of(day) != "train":
        raise SystemExit("a training day only")
    p = prints(day)
    q, lat = PRIMARY
    res = {
        "day": day,
        "runs": [r.name for r in runs],
        "cell": f"{q}/{lat}",
        "label": "SMOKE: one training day, lower bound on overfilled fills (Q3)",
    }
    for label in LABELS:
        paths = [r / f"fills_{label}_{q}_{lat}_{day}.parquet" for r in runs]
        path = next((x for x in paths if x.exists()), None)
        if path is not None:
            res[label] = {"run": path.parent.name, **summary(classify(pl.read_parquet(path), p))}
    out = ROOT / "docs" / "smoke" / f"partial_fill_bound_{day}.json"
    out.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], [Path(a) for a in sys.argv[2:]])
