"""Market-order events: prints with the same exchange timestamp and aggressor side are one
order that swept the book, so they collapse into one event (PREREGISTRATION.md section 5).

Usage: uv run python -m toxic_flow.events.market_orders YYYY-MM-DD
Writes data/events/<date>.parquet with columns (exch_ts, local_ts, side, size, vwap,
n_prints, levels); times in nanoseconds like hftbacktest. Side "b" is buyer-initiated,
"s" seller-initiated. Without collapsing, one aggressive order hitting five levels would
count as five arrivals at the same instant, which a Hawkes likelihood cannot represent.
"""

import json
import sys
from pathlib import Path

import polars as pl

from toxic_flow.data.download import RAW
from toxic_flow.data.split_lock import assert_allowed, normalise

ROOT = Path(__file__).resolve().parents[3]
EVENTS = ROOT / "data" / "events"
CONVERTED = ROOT / "data" / "converted"
SCHEMA = {
    "exch_ts": pl.Int64,
    "local_ts": pl.Int64,
    "side": pl.String,
    "size": pl.Float64,
    "vwap": pl.Float64,
    "n_prints": pl.Int64,
    "levels": pl.Int64,
}


def collapse(trades_csv: Path, local_offset_ns: int = 0) -> tuple[pl.DataFrame, dict]:
    """One row per (exchange timestamp, side). Returns (events, stats).

    local_ts is the last print's local time: the event is complete only once its last
    print has arrived. local_offset_ns is the day's correct_local_timestamp shift, so the
    events share the simulator's local clock.
    """
    prints = pl.read_csv(
        trades_csv,
        columns=["timestamp", "local_timestamp", "side", "price", "amount"],
        schema_overrides={"timestamp": pl.Int64, "local_timestamp": pl.Int64},
    )
    known = prints.filter(pl.col("side").is_in(["buy", "sell"]))
    events = (
        known.group_by(["timestamp", "side"])
        .agg(
            (pl.col("local_timestamp").max() * 1000 + local_offset_ns).alias("local_ts"),
            pl.col("amount").sum().alias("size"),
            ((pl.col("price") * pl.col("amount")).sum() / pl.col("amount").sum()).alias("vwap"),
            pl.len().cast(pl.Int64).alias("n_prints"),
            pl.col("price").n_unique().cast(pl.Int64).alias("levels"),
        )
        .with_columns(
            (pl.col("timestamp") * 1000).alias("exch_ts"),
            pl.when(pl.col("side") == "buy").then(pl.lit("b")).otherwise(pl.lit("s")).alias("side"),
        )
        .select(list(SCHEMA))
        .cast(SCHEMA)
        .sort(["local_ts", "exch_ts", "side"])
    )
    stats = {
        "prints": prints.height,
        "unknown_side": prints.height - known.height,
        "events": events.height,
        "collapse_ratio": round(known.height / events.height, 4) if events.height else None,
        "multi_print_events": int((events["n_prints"] > 1).sum()),
        "max_prints_in_event": int(events["n_prints"].max()) if events.height else 0,
    }
    return events, stats


def write_events(events: pl.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    events.write_parquet(path)
    return path


def build_day(day: str, raw_dir: Path = RAW, out_dir: Path = EVENTS, offset_ns=None) -> dict:
    """offset_ns: the day's local-timestamp offset from conversion; read from convert.json
    when not given, 0 if the day was never converted."""
    assert_allowed(day)  # first: this reads the raw trades file
    day = normalise(day)
    info = CONVERTED / day / "convert.json"
    if offset_ns is not None:
        offset = offset_ns
    else:
        offset = json.loads(info.read_text())["local_ts_offset_ns"] if info.exists() else 0
    events, stats = collapse(raw_dir / day / "trades.csv.gz", local_offset_ns=offset)
    write_events(events, out_dir / f"{day}.parquet")
    return {**stats, "local_ts_offset_ns": offset}


if __name__ == "__main__":
    print(json.dumps(build_day(sys.argv[1]), indent=2))
