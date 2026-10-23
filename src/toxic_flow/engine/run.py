"""Run one config over its grid and write results/<config_hash>/ (SPEC.md M2).

Usage: uv run python -m toxic_flow.engine.run configs/runs/<name>.yaml   (make run CFG=...)

The config must be tracked by git and the working tree clean, so every result maps to a
commit. results/<hash>/ gets config.yaml, meta.json (commit, time, versions),
metrics.parquet (one row per day and cell) and fills_<cell>.parquet (gitignored).
Fees are zero in the simulation and applied in evaluation (PREREGISTRATION.md section 3).
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import hftbacktest
import numpy as np
import polars as pl
import yaml
from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
from hftbacktest.data.utils.feed_order_latency import generate_order_latency

from toxic_flow.data.convert import CONVERTED
from toxic_flow.data.split_lock import assert_allowed
from toxic_flow.data.venue import venue_for
from toxic_flow.engine.grid import LATENCY_MUL, QUEUE_MODELS, config_hash, expand
from toxic_flow.eval.markouts import HORIZONS_S, markouts
from toxic_flow.eval.metrics import day_metrics
from toxic_flow.strategies.b0_fixed import run_b0
from toxic_flow.strategies.b1_glft import run_b1
from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
MAX_STEPS, MAX_FILLS = 900_000, 500_000
OUT_SLOTS = 13


def utc_ns(day: str, hms: str) -> int:
    return int(datetime.fromisoformat(f"{day}T{hms}+00:00").timestamp()) * 10**9


def latency_file(day: str, setting: str) -> Path:
    """Order latency from feed latency at the setting's multiplier, built once per day."""
    path = CONVERTED / day / f"order_latency_{setting}.npz"
    if not path.exists():
        mul = LATENCY_MUL[setting]
        parts = json.loads((CONVERTED / day / "convert.json").read_text())["files"]
        lat = [
            generate_order_latency(str(CONVERTED / day / f), mul_entry=mul, mul_resp=mul)
            for f in parts
        ]
        np.savez_compressed(path, data=np.concatenate(lat))
    return path


def build_backtest(day: str, queue: str, latency: str, maker_fee=0.0, taker_fee=0.0):
    venue = venue_for(day)
    parts = json.loads((CONVERTED / day / "convert.json").read_text())["files"]
    asset = BacktestAsset().data([str(CONVERTED / day / f) for f in parts]).linear_asset(1.0)
    if latency == "zero":
        asset = asset.constant_order_latency(0, 0)
    else:
        # A path, not an array: hftbacktest keeps a raw pointer to an array argument.
        asset = asset.intp_order_latency(str(latency_file(day, latency)))
    method, args = QUEUE_MODELS[queue]
    asset = getattr(asset, method)(*args)
    asset = (
        asset.no_partial_fill_exchange()
        .trading_value_fee_model(maker_fee, taker_fee)
        .tick_size(venue["tick_size"])
        .lot_size(venue["lot_size"])
        .last_trades_capacity(10_000)  # B1 reads the trades of each step
    )
    return HashMapMarketDepthBacktest([asset])


def run_cell(cell: dict, cfg: dict, maker_fee_bps: float = 0.0) -> tuple[dict, pl.DataFrame]:
    """One day of one strategy in one queue-model and latency cell. Returns (metrics row,
    fills with markouts). maker_fee_bps puts a fee into hftbacktest itself (AC2.3 test)."""
    day = cell["day"]
    assert_allowed(day)
    venue = venue_for(day)
    s = cell["strategy"]
    start, end = utc_ns(day, cfg["quote_start"]), utc_ns(day, cfg["quote_end"])
    step = int(cfg["step_ns"])
    steps, fills, out = (
        np.zeros(MAX_STEPS, STEP_DTYPE),
        np.zeros(MAX_FILLS, FILL_DTYPE),
        np.zeros(OUT_SLOTS),
    )
    hbt = build_backtest(
        day, cell["queue"], cell["latency"], maker_fee_bps / 1e4, venue["taker_fee_bps"] / 1e4
    )
    t0 = time.perf_counter()
    common = (venue["lot_size"], venue["min_notional"], int(cfg["max_lots"]))
    try:
        if s["name"] == "B0":
            run_b0(hbt, int(s["h"]), *common, start, end, step, steps, fills, out)
        elif s["name"] == "B1":
            window = int(float(s["window_s"]) * 1e9 / step)
            run_b1(hbt, float(s["gamma"]), window, int(s.get("update_every", 50)), *common,
                   start, end, step, steps, fills, out)  # fmt: skip
        else:
            raise ValueError(f"unknown strategy {s['name']}")
    finally:
        hbt.close()
    wall = time.perf_counter() - t0
    steps, fills = steps[: int(out[0])], fills[: int(out[12])]
    fee_levels = {
        name: venue["maker_fee_bps"] if f == "venue" else float(f)
        for name, f in cfg["fee_levels_bps"].items()
    }
    m = day_metrics(
        fills, steps, mark_mid=out[4], order_qty=out[5], fee_levels_bps=fee_levels,
        funding_ns=[utc_ns(day, "08:00:00"), utc_ns(day, "16:00:00")],
    )  # fmt: skip
    mk = markouts(fills, steps)
    row = {
        "day": day,
        "strategy": s["name"],
        "params": json.dumps(s, sort_keys=True),
        "queue": cell["queue"],
        "latency": cell["latency"],
        **{k: v for k, v in m.items() if k not in ("net_pnl", "inventory_at_funding")},
        **{f"net_pnl_{k}": v for k, v in m["net_pnl"].items()},
        "inventory_at_0800": m["inventory_at_funding"][0],
        "inventory_at_1600": m["inventory_at_funding"][1],
        **{
            f"mean_markout_{h}s_bps": float(np.nanmean(mk[f"markout_{h}s_bps"]))
            if len(fills)
            else float("nan")
            for h in HORIZONS_S
        },  # fmt: skip
        "order_qty": out[5],
        "mark_mid": out[4],
        "max_orders_one_side": int(out[6]),
        "max_inventory_lots": int(out[7]),
        "engine_fills": int(out[1]),
        "engine_position": out[2],
        "engine_cash": out[3],
        "engine_fee": out[10],
        "engine_traded_value": out[11],
        "wall_seconds": round(wall, 1),
    }
    fills_df = pl.DataFrame({name: fills[name] for name in FILL_DTYPE.names} | mk)
    return row, fills_df


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


def run_config(cfg_path: Path) -> Path:
    rel = Path(cfg_path).resolve().relative_to(ROOT).as_posix()
    if not _git("ls-files", "--", rel).strip():
        raise SystemExit(f"{rel} is not tracked by git; commit the config first")
    if _git("status", "--porcelain").strip():
        raise SystemExit("working tree has changes; results must map to a commit")
    cfg = yaml.safe_load(Path(cfg_path).read_text())
    out_dir = RESULTS / config_hash(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.yaml").write_text(Path(cfg_path).read_text())
    meta = {
        "config": rel,
        "config_hash": config_hash(cfg),
        "commit": _git("rev-parse", "HEAD").strip(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hftbacktest": hftbacktest.__version__,
        "label": cfg.get("label", ""),
    }
    rows = []
    for cell in expand(cfg):
        row, fills = run_cell(cell, cfg)
        name = f"{row['strategy']}_{cell['queue']}_{cell['latency']}_{cell['day']}"
        fills.write_parquet(out_dir / f"fills_{name}.parquet")
        rows.append(row)
        print(
            f"{name}: {row['fills']} fills, BEF {row['break_even_fee_bps']:.3f} bp, {row['wall_seconds']} s"
        )
    pl.DataFrame(rows).write_parquet(out_dir / "metrics.parquet")
    meta["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return out_dir


if __name__ == "__main__":
    print(run_config(Path(sys.argv[1])))
