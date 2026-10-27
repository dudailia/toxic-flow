#!/usr/bin/env python3
"""One minute of the simulation for the project page: site/replay_window.json.

Usage: uv run python scripts/site_replay.py   (make site-data)

The window is fixed by a rule written before any of its data was looked at (Ilia,
2026-10-26): the first full minute after 12:00 UTC on 2024-06-01, a training day, so
[12:00:00, 12:01:00) UTC. It is not chosen to show anything.

What it holds, at the 100 ms decision steps of that minute (simulator's local clock):
the top 5 book levels as the strategies saw them, the trades (prints, exchange time),
the quotes and fills of B1, B3 and F, B3's Hawkes intensities lambda_b and lambda_s, the
decay-weighted counts of B2b's EWMA signal, and the steps where B3 or F pulled a side.
The strategies are those of the committed configs/runs/v2_fill_hold_val.yaml (B1, B3 at
the selected settings, F at the frozen hold) in the primary cell, run on the whole day by
engine.run.run_cell. The script stops unless each one's day result equals the committed
training-day result for 2024-06-01 (B1 in results/4db60c584c71, B3 in 58c46cc49981, F at
0.1 s in 83bb2b991997), so the minute shown is a minute of runs already reported. Fills
are simulated: no order was sent to an exchange.
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from toxic_flow.data.convert import evict_converted
from toxic_flow.data.download import RAW
from toxic_flow.data.venue import venue_for
from toxic_flow.engine.run import build_backtest, event_inputs, run_cell, utc_ns
from toxic_flow.signals.ewma import ewma_at
from toxic_flow.signals.hawkes_online import hawkes_at

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "replay_window.json"
CONFIG = ROOT / "configs" / "runs" / "v2_fill_hold_val.yaml"
DAY, START, END = "2024-06-01", "12:00:00", "12:01:00"
CELL = ("risk_averse", "high")
LEVELS = 5
MAX_BYTES = 3_000_000
# The committed day result each strategy must reproduce: (results hash, label there).
REPRODUCE = {"B1": ("4db60c584c71", "B1"), "B3": ("58c46cc49981", "B3"), "F": ("83bb2b991997", "F_h0.1")}  # fmt: skip


def committed_row(h: str, label: str) -> dict:
    m = pl.read_parquet(ROOT / "results" / h / "metrics.parquet")
    m = m if "label" in m.columns else m.with_columns(label=pl.col("strategy"))
    r = m.filter((pl.col("label") == label) & (pl.col("day") == DAY)
                 & (pl.col("queue") == CELL[0]) & (pl.col("latency") == CELL[1]))  # fmt: skip
    if r.height != 1:
        raise SystemExit(f"results/{h} has {r.height} rows for {label} on {DAY}")
    return r.row(0, named=True)


def ms(ts, w0: int) -> float:
    return round((int(ts) - w0) / 1e6, 3)


def book(w0: int, step: int, n: int, tick: float) -> list[dict]:
    """Top LEVELS levels each side at each step, the local view after feed latency."""
    hbt = build_backtest(DAY, *CELL)
    out = []
    try:
        hbt.elapse(w0 - hbt.current_timestamp)
        for k in range(n):
            if k:
                hbt.elapse(step)
            d = hbt.depth(0)
            sides = {}
            for name, best, sign, qty in (("bids", d.best_bid_tick, -1, d.bid_qty_at_tick),
                                          ("asks", d.best_ask_tick, 1, d.ask_qty_at_tick)):  # fmt: skip
                levels, t = [], best
                while len(levels) < LEVELS and abs(t - best) < 1000:
                    if qty(t) > 0:
                        levels.append([round(t * tick, 1), round(float(qty(t)), 3)])
                    t += sign
                sides[name] = levels
            out.append({"t_ms": ms(hbt.current_timestamp, w0), **sides})
    finally:
        hbt.close()
    return out


def trades(w0: int, w1: int) -> list[dict]:
    tr = pl.read_csv(RAW / DAY / "trades.csv.gz",
                     columns=["timestamp", "side", "price", "amount"],
                     schema_overrides={"timestamp": pl.Int64})  # fmt: skip
    tr = tr.with_columns(exch_ts=pl.col("timestamp") * 1000).filter(
        (pl.col("exch_ts") >= w0) & (pl.col("exch_ts") < w1)
    )
    return [{"t_ms": ms(t, w0), "side": s, "price": p, "qty": q}
            for t, s, p, q in tr.select("exch_ts", "side", "price", "amount").iter_rows()]  # fmt: skip


def pulls(steps: np.ndarray, w0: int, step: int) -> list[dict]:
    """Each run of steps with a side marked toxic: +1 the ask was not quoted, -1 the bid."""
    out, t = [], steps["toxic"]
    for i in range(len(t)):
        if t[i] != 0 and (i == 0 or t[i - 1] != t[i]):
            j = i
            while j + 1 < len(t) and t[j + 1] == t[i]:
                j += 1
            out.append({"start_ms": ms(steps["ts"][i], w0), "end_ms": ms(steps["ts"][j] + step, w0),
                        "side": "ask" if t[i] == 1 else "bid"})  # fmt: skip
    return out


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text())
    w0, w1 = utc_ns(DAY, START), utc_ns(DAY, END)
    step, tick = int(cfg["step_ns"]), venue_for(DAY)["tick_size"]
    strategies, b3 = {}, None
    try:
        for s in cfg["strategies"]:
            keep = {}
            row, _ = run_cell({"day": DAY, "queue": CELL[0], "latency": CELL[1], "strategy": s},
                              cfg, keep=keep)  # fmt: skip
            want = committed_row(*REPRODUCE[s["name"]])
            if (
                row["fills"] != want["fills"]
                or abs(row["break_even_fee_bps"] - want["break_even_fee_bps"]) > 1e-9
            ):
                raise SystemExit(f"{s['name']} on {DAY} does not reproduce results/{REPRODUCE[s['name']][0]}")  # fmt: skip
            st, f = keep["steps"], keep["fills"]
            st = st[(st["ts"] >= w0) & (st["ts"] < w1)]
            f = f[(f["local_ts"] >= w0) & (f["local_ts"] < w1)]
            px = lambda x: None if np.isnan(x) else round(float(x) * tick, 1)  # noqa: E731
            strategies[s["name"]] = {
                "params": {k: v for k, v in s.items() if k in ("name", "p", "k_ticks", "hold_s")},
                "day_result": {"fills": row["fills"], "break_even_fee_bps": row["break_even_fee_bps"],
                               "reproduces": f"results/{REPRODUCE[s['name']][0]}/metrics.parquet"},
                "quotes": [{"t_ms": ms(r["ts"], w0), "bid": px(r["bid_tick"]), "ask": px(r["ask_tick"]),
                            "position": float(r["position"])} for r in st],
                "fills": [{"t_ms": ms(r["local_ts"], w0), "exch_t_ms": ms(r["exch_ts"], w0),
                           "side": "buy" if r["side"] == 1 else "sell", "price": float(r["price"]),
                           "qty": float(r["qty"]), "simulated": True} for r in f],
                "pulls": pulls(st, w0, step),
            }  # fmt: skip
            if s["name"] == "B3":
                b3 = s
        grid = np.array([q["t_ms"] for q in strategies["B1"]["quotes"]])
        decision = (w0 + np.round(grid * 1e6)).astype(np.int64)
        ev_ts, ev_side = event_inputs(DAY)
        mu = np.array([b3["mu_b"], b3["mu_s"]])
        alpha = np.array([[b3["alpha_bb"], b3["alpha_bs"]], [b3["alpha_sb"], b3["alpha_ss"]]])
        lam = hawkes_at(ev_ts, ev_side, decision, mu, alpha, float(b3["beta"]))
        tau = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())["B2b"]["tau_s"]
        u, a = ewma_at(ev_ts, ev_side, decision, float(tau))
        book_rows = book(w0, step, len(decision), tick)
        trade_rows = trades(w0, w1)
    finally:
        evict_converted(DAY)
    out = {
        "note": "Simulated quotes and fills on historical data: no order was sent to an "
        "exchange. Times are milliseconds from the window start, on the simulator's local "
        "clock, except trades, which are on exchange time.",
        "rule": "The first full minute after 12:00 UTC on 2024-06-01, fixed before its data was looked at.",
        "day": DAY, "window_utc": [START, END], "window_start_ns": w0, "step_ms": step / 1e6,
        "cell": "/".join(CELL), "config": "configs/runs/v2_fill_hold_val.yaml",
        "book_levels": LEVELS, "book": book_rows, "trades": trade_rows,
        "signals": {
            "t_ms": grid.tolist(),
            "hawkes_lambda_b": [round(float(x), 4) for x in lam[:, 0]],
            "hawkes_lambda_s": [round(float(x), 4) for x in lam[:, 1]],
            "ewma_tau_s": tau,
            # B2b's decay-weighted counts of buyer- and seller-initiated market orders.
            "ewma_count_b": [round(float(x * (1 + v) / 2), 4) for x, v in zip(a, u, strict=True)],
            "ewma_count_s": [round(float(x * (1 - v) / 2), 4) for x, v in zip(a, u, strict=True)],
        },
        "strategies": strategies,
    }  # fmt: skip
    text = json.dumps(out, separators=(",", ":"), sort_keys=True) + "\n"
    if len(text.encode()) > MAX_BYTES:
        raise SystemExit(f"replay window is {len(text.encode())} bytes, over {MAX_BYTES}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text)
    print(OUT, f"{len(text.encode()) / 1e6:.2f} MB")


if __name__ == "__main__":
    sys.exit(main())
