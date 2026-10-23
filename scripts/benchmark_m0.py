#!/usr/bin/env python3
"""M0 benchmark: B0 at h = 1 tick on 2024-01-01, risk-averse queue, low latency.

Usage: uv run python scripts/benchmark_m0.py
Writes data/benchmark_m0.json. Measures cost, not performance: the PnL it records is
there only so M2 can check the accounting, and is not a result of the study.
"""

import json
import multiprocessing
import platform
import resource
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import hftbacktest
import numpy as np
from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
from hftbacktest.data.utils.feed_order_latency import generate_order_latency

from toxic_flow.data.convert import CONVERTED
from toxic_flow.data.split_lock import assert_allowed
from toxic_flow.data.venue import venue_for
from toxic_flow.machine import peak_rss_bytes
from toxic_flow.strategies.b0_fixed import run_b0
from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE

ROOT = Path(__file__).resolve().parents[1]
DAY = "2024-01-01"
H_TICKS = 1
MAX_LOTS = 10  # inventory cap Q = 10 order sizes (PREREGISTRATION.md section 3)
STEP_NS = 100_000_000  # decision step 100 ms
LATENCY_MUL = 1.0  # "low": order entry and response latency = observed feed latency


def utc_ns(day: str, hh: int, mm: int) -> int:
    return int(datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}:00+00:00").timestamp()) * 10**9


def sysctl(name: str) -> str:
    return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True).stdout.strip()


def available_ram_bytes() -> int:
    """Free plus inactive plus speculative pages from vm_stat: what a new run could use."""
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout.splitlines()
    page = int(out[0].split("page size of")[1].split()[0])
    pages = {ln.split(":")[0]: int(ln.split(":")[1].strip(" .")) for ln in out[1:] if ":" in ln}
    keys = ("Pages free", "Pages inactive", "Pages speculative")
    return page * sum(pages[k] for k in keys)


def build(parts: list[Path], lat_file: Path, venue: dict):
    # Paths, not arrays: hftbacktest keeps a raw pointer to an ndarray argument without
    # copying it (py-hftbacktest/src/lib.rs, _intp_order_latency_ndarray).
    asset = (
        BacktestAsset()
        .data([str(p) for p in parts])
        .linear_asset(1.0)
        .intp_order_latency(str(lat_file))
        .risk_adverse_queue_model()
        # partial_fill_exchange() panics on this day in 2.4.4; see docs/ENGINE.md.
        .no_partial_fill_exchange()
        .trading_value_fee_model(0.0, 0.0)  # fees are applied in evaluation
        .tick_size(venue["tick_size"])
        .lot_size(venue["lot_size"])
    )
    return HashMapMarketDepthBacktest([asset])


def records():
    """Per-step and per-fill arrays, and the 13 totals, for run_b0."""
    return np.zeros(900_000, STEP_DTYPE), np.zeros(500_000, FILL_DTYPE), np.zeros(13)


def backtest(parts: list[Path], lat_file: Path, venue: dict, queue) -> None:
    args = (H_TICKS, venue["lot_size"], venue["min_notional"], MAX_LOTS)
    window = (utc_ns(DAY, 0, 30), utc_ns(DAY, 23, 59), STEP_NS)

    # Compile once on the first part with an empty quoting window, so the timed run below
    # measures the loop and not numba.
    t0 = time.perf_counter()
    hbt = build(parts[:1], lat_file, venue)
    first = int(np.load(parts[0])["data"]["local_ts"][0])
    run_b0(hbt, *args, first, first, STEP_NS, *records())
    hbt.close()
    compile_seconds = time.perf_counter() - t0

    steps, fills, out = records()
    t0 = time.perf_counter()
    hbt = build(parts, lat_file, venue)
    run_b0(hbt, *args, *window, steps, fills, out)
    hbt.close()
    queue.put((out, compile_seconds, time.perf_counter() - t0))


def main() -> None:
    assert_allowed(DAY)
    venue = venue_for(DAY)
    day_dir = CONVERTED / DAY
    parts = sorted(day_dir.glob("part-*.npz"))
    convert_info = json.loads((day_dir / "convert.json").read_text())

    t0 = time.perf_counter()
    latency = np.concatenate(
        [generate_order_latency(str(p), mul_entry=LATENCY_MUL, mul_resp=LATENCY_MUL) for p in parts]
    )
    latency_seconds = time.perf_counter() - t0

    entry_ms = (latency["exch_ts"] - latency["req_ts"]) / 1e6
    lat_file = day_dir / "order_latency_low.npz"
    np.savez_compressed(lat_file, data=latency)

    # The backtest runs in a fresh process so its peak memory is measured on its own,
    # without the order-latency build above. That is the figure parallel runs need.
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    child = ctx.Process(target=backtest, args=(parts, lat_file, venue, queue))
    child.start()
    child.join()  # the result is a few numbers, so joining before reading cannot block
    if child.exitcode != 0:
        raise RuntimeError(f"backtest process exited with code {child.exitcode}")
    result = queue.get(timeout=10)
    child_rss = peak_rss_bytes(resource.RUSAGE_CHILDREN)
    out, compile_seconds, loop_seconds = result

    steps, fills, position, balance, mid, qty, max_side, max_lots = out[:8]
    report = {
        "date": DAY,
        "strategy": "B0 h=1 tick, post-only, one order per side",
        "queue_model": "risk_adverse_queue_model()",
        "exchange_model": "no_partial_fill_exchange()",
        "latency": f"intp_order_latency, generate_order_latency mul={LATENCY_MUL}",
        "decision_step_ns": STEP_NS,
        "quote_window_utc": ["00:30:00", "23:59:00"],
        "order_qty_btc": round(float(qty), 6),
        "steps_quoted": int(steps),
        "fill_count": int(fills),
        "end_position_btc": round(float(position), 6),
        "max_orders_on_one_side": int(max_side),
        "max_inventory_lots": int(max_lots),
        "gross_pnl_usdt_not_a_result": round(float(balance + position * mid), 4),
        "loop_wall_seconds": round(loop_seconds, 1),
        "compile_and_first_part_seconds": round(compile_seconds, 1),
        "order_latency_build_seconds": round(latency_seconds, 1),
        "order_latency_rows": len(latency),
        # Entry latency in ms (= feed latency at mul 1). The largest sample is the
        # start-of-day REST snapshot, not network latency; see docs/ENGINE.md.
        "order_entry_latency_ms": {
            "first_sample": round(float(entry_ms[0]), 3),
            **{f"p{q}": round(float(np.percentile(entry_ms, q)), 3) for q in (50, 90, 99)},
            "max": round(float(entry_ms.max()), 3),
        },
        "backtest_peak_rss_bytes": child_rss,
        "latency_build_peak_rss_bytes": peak_rss_bytes(),
        "events": sum(convert_info["events_per_part"]),
        "raw_bytes": convert_info["raw_bytes"],
        "converted_bytes": convert_info["converted_bytes"],
        "conversion_seconds": convert_info["conversion_seconds"],
        "machine": {
            "cpu": sysctl("machdep.cpu.brand_string"),
            "cores": int(sysctl("hw.ncpu")),
            "performance_cores": int(sysctl("hw.perflevel0.physicalcpu") or 0),
            "efficiency_cores": int(sysctl("hw.perflevel1.physicalcpu") or 0),
            "ram_bytes": int(sysctl("hw.memsize")),
            "os": platform.platform(),
            "python": platform.python_version(),
            "hftbacktest": hftbacktest.__version__,
        },
        "available_ram_bytes_at_end": available_ram_bytes(),
        "free_disk_bytes_at_end": shutil.disk_usage(ROOT).free,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    out_path = ROOT / "data" / "benchmark_m0.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
