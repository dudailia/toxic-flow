"""Run one config over its grid and write results/<config_hash>/ (SPEC.md M2).

Usage: uv run python -m toxic_flow.engine.run configs/runs/<name>.yaml   (make run CFG=...)

The config must be tracked by git and the working tree clean, so every result maps to a
commit. results/<hash>/ gets config.yaml, meta.json (commit, time, versions),
metrics.parquet (one row per day and cell) and fills_<cell>.parquet (gitignored).
Fees are zero in the simulation and applied in evaluation (PREREGISTRATION.md section 3).
"""

import fcntl
import functools
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import hftbacktest
import numpy as np
import polars as pl
import yaml
from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
from hftbacktest.data.utils.feed_order_latency import generate_order_latency

from toxic_flow.data.convert import CONVERTED
from toxic_flow.data.download import RAW
from toxic_flow.data.split_lock import assert_allowed
from toxic_flow.data.venue import venue_for
from toxic_flow.engine.grid import LATENCY_MUL, QUEUE_MODELS, config_hash, expand
from toxic_flow.eval.markouts import HORIZONS_S, markouts
from toxic_flow.eval.metrics import day_metrics, no_print_share, quote_metrics, window_metrics
from toxic_flow.signals.hawkes_fit import rescale_decay
from toxic_flow.signals.normalise import NORM_STEPS
from toxic_flow.strategies.b0_fixed import run_b0
from toxic_flow.strategies.common import FILL_DTYPE, STEP_DTYPE
from toxic_flow.strategies.overlay import EWMA, EXTERNAL, HAWKES, NONE, OFI, run_b1, run_overlay
from toxic_flow.strategies.touch import PULL, run_touch

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
MAX_STEPS, MAX_FILLS = 900_000, 500_000
OUT_SLOTS = 13


def utc_ns(day: str, hms: str) -> int:
    return int(datetime.fromisoformat(f"{day}T{hms}+00:00").timestamp()) * 10**9


# The child's exit code when the memory guard refuses; the run then waits and asks again
# for up to MEMORY_WAIT_S before failing (Ilia, 2026-10-24: memory below what the guard
# needs for 30 minutes is reported, not worked around).
MEMORY_REFUSED = 75
MEMORY_WAIT_S, MEMORY_RETRY_S = 30 * 60, 60


def day_parts(day: str, sleep=time.sleep) -> list[str]:
    """A day's converted parts, from the cache in data/converted/<day>. A day not in the
    cache is converted from its hashed raw files first, in a child process so the run's own
    process never holds the conversion's memory (data/convert.py: disk and memory guards,
    events hash checked against the manifest)."""
    dest = CONVERTED / day
    if not (dest / "convert.json").exists():
        # One conversion at a time, also across runs on different days (Ilia's rule): the
        # memory guard checks free memory at the start, which a parallel conversion would
        # then take, and conversions write the shared manifest.
        CONVERTED.mkdir(parents=True, exist_ok=True)
        with open(CONVERTED / ".convert.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not (dest / "convert.json").exists():
                # The disk floor for a conversion, 12 GB unless Ilia lowers it for a block
                # (2026-10-25: "continue until it is 3 GB"); the memory guard is unchanged.
                min_free = int(float(os.environ.get("TOXIC_FLOW_MIN_FREE_GB", "12")) * 1e9)
                code = (
                    "import sys\nfrom toxic_flow.data.convert import MemoryGuardError, convert_day\n"
                    f"try:\n    convert_day({day!r}, min_free={min_free})\nexcept MemoryGuardError as e:\n"
                    f"    print(e, file=sys.stderr)\n    sys.exit({MEMORY_REFUSED})"
                )
                waited = 0
                while True:
                    rc = subprocess.run([sys.executable, "-c", code]).returncode
                    if rc != MEMORY_REFUSED:
                        break
                    if waited >= MEMORY_WAIT_S:
                        raise SystemExit(
                            f"{day}: memory below the guard's need for {waited // 60} min"
                        )
                    sleep(MEMORY_RETRY_S)
                    waited += MEMORY_RETRY_S
                if rc != 0:
                    raise subprocess.CalledProcessError(rc, "convert_day")
    return [str(dest / f) for f in json.loads((dest / "convert.json").read_text())["files"]]


def _as_feed_file(part):
    """generate_order_latency np.loads its argument, so an array goes in as an npz buffer."""
    if isinstance(part, str):
        return part
    buf = io.BytesIO()
    np.savez(buf, data=part)
    buf.seek(0)
    return buf


def latency_file(day: str, setting: str) -> Path:
    """Order latency from feed latency at the setting's multiplier, built once per day."""
    path = CONVERTED / day / f"order_latency_{setting}.npz"
    if not path.exists():
        mul = LATENCY_MUL[setting]
        lat = [
            generate_order_latency(_as_feed_file(p), mul_entry=mul, mul_resp=mul)
            for p in day_parts(day)
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, data=np.concatenate(lat))
    return path


def event_inputs(day: str) -> tuple[np.ndarray, np.ndarray]:
    """Market-order events of the day (local_ts sorted, side 0 b / 1 s), built once."""
    from toxic_flow.events.market_orders import EVENTS, build_day

    path = EVENTS / f"{day}.parquet"
    if not path.exists():
        build_day(day)
    ev = pl.read_parquet(path, columns=["local_ts", "side"])
    return ev["local_ts"].to_numpy(), (ev["side"] == "s").to_numpy().astype(np.int64)


@functools.lru_cache(maxsize=1)
def opposite_prints(day: str) -> dict:
    """For eval.metrics.no_print_share (Q50): per exchange time, the highest
    buyer-initiated and the lowest seller-initiated print of the day, from the hashed raw
    trades. Cached for the day's cells, which expand() runs one after another."""
    assert_allowed(day)
    tr = pl.read_csv(
        RAW / day / "trades.csv.gz",
        columns=["timestamp", "side", "price"],
        schema_overrides={"timestamp": pl.Int64},
    ).with_columns(exch_ts=pl.col("timestamp") * 1000)  # microseconds, like the events
    out = {}
    for agg, side, through in (
        ("b", "buy", pl.col("price").max()),
        ("s", "sell", pl.col("price").min()),
    ):
        g = tr.filter(pl.col("side") == side).group_by("exch_ts").agg(through).sort("exch_ts")
        out[agg] = (g["exch_ts"].to_numpy(), g["price"].to_numpy())
    return out


def ofi_inputs(day: str) -> tuple[np.ndarray, np.ndarray]:
    """Best-level OFI contributions of the day (update times, cumulative sum from 0)."""
    from toxic_flow.data.book import replay_bbo
    from toxic_flow.signals.ofi import ofi_contributions

    path = CONVERTED / day / "ofi_contributions.npz"
    if not path.exists():
        venue = venue_for(day)
        bbo, _ = replay_bbo(day_parts(day), venue["tick_size"], venue["lot_size"])
        ts, e = ofi_contributions(bbo)
        np.savez_compressed(path, ts=ts, e=e)
    data = np.load(path)
    return data["ts"], np.concatenate([[0.0], np.cumsum(data["e"])])


def shuffled_sides(side: np.ndarray, seed: int = 1729) -> np.ndarray:
    """Canary C1: the day's event sides randomly permuted, so counts stay and signs carry
    no information (PREREGISTRATION.md section 10)."""
    return np.random.default_rng(seed).permutation(side)


def random_pulls(
    day: str, start_ns: int, end_ns: int, step_ns: int, rate: float, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """R, random pulls (C1's control, PREREGISTRATION.md section 10): a series (time, u, m)
    on the 100 ms step grid where each step independently marks a side toxic with
    probability rate, the ask or the bid with equal chance. It reads no market data, so it
    carries no information; it measures what pulling at that rate costs by itself. The
    grid starts one step early so the first quoting step has a point at or before it."""
    ts = np.arange(start_ns - step_ns, end_ns + step_ns, step_ns, dtype=np.int64)
    rng = np.random.default_rng([seed, int(day.replace("-", ""))])
    pull = rng.random(len(ts)) < rate
    side = np.where(rng.random(len(ts)) < 0.5, 1.0, -1.0)
    return ts, np.where(pull, side, 0.0), np.zeros(len(ts))


def run_length_pulls(
    day: str, start_ns: int, end_ns: int, step_ns: int, rate: float, episodes: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RL, random pulls matched on run length as well as rate (exploratory, section 10):
    a two-state chain on random_pulls' grid. A pulled run lasts a geometric number of steps
    with mean L = rate * steps / episodes, and the gap between runs a geometric number with
    mean L (1 - rate) / rate, so in expectation a share rate of the steps is pulled in
    episodes runs, as in the strategy RL controls for on that day. R starts a new run at
    almost every pulled step, which costs the queue place each time; RL does not. Each run
    pulls one side, the ask or the bid with equal chance, and it reads no market data."""
    ts = np.arange(start_ns - step_ns, end_ns + step_ns, step_ns, dtype=np.int64)
    u = np.zeros(len(ts))
    if rate == 0 or episodes == 0:
        return ts, u, np.zeros(len(ts))
    if not 0 < rate < 0.5:
        raise ValueError(f"rate {rate} outside (0, 0.5)")
    # The strategy has at least one pulled step per run; L can fall just under 1 only
    # because this grid has a point or two more than the strategy's quoting steps.
    run = max(rate * len(ts) / episodes, 1.0)
    gap = run * (1 - rate) / rate  # at least 1, since run >= 1 and rate < 0.5
    rng = np.random.default_rng([seed, int(day.replace("-", ""))])
    pulled = rng.random() < rate  # the chain starts in its stationary state
    i = 0
    while i < len(ts):
        n = int(rng.geometric(1 / run if pulled else 1 / gap))
        if pulled:
            u[i : i + n] = 1.0 if rng.random() < 0.5 else -1.0
        i += n
        pulled = not pulled
    return ts, u, np.zeros(len(ts))


def _signal_inputs(s: dict, day: str) -> tuple:
    """Signal mode and input streams for B2, B2b, B3 and the canaries built on B3: C1 (B3
    on shuffled sides) and C4 (B3 with the decay rescaled). Returns (mode, sig_ts,
    sig_side, cum, tau_s, ofi_window_ns, mu, alpha, beta)."""
    mu, alpha, beta = np.zeros(2), np.zeros((2, 2)), 1.0
    tau, ofi_window = 1.0, 1
    if s["name"] == "B2":
        mode = OFI
        sig_ts, cum = ofi_inputs(day)
        sig_side = np.zeros(len(sig_ts), np.int64)
        ofi_window = int(float(s["ofi_window_s"]) * 1e9)
    else:
        sig_ts, sig_side = event_inputs(day)
        cum = np.zeros(1)
        if s["name"] == "B2b":
            mode, tau = EWMA, float(s["tau_s"])
        elif s["name"] in ("B3", "C1", "C4"):
            mode = HAWKES
            p = rescale_decay(s, float(s["decay_factor"])) if s["name"] == "C4" else s
            mu = np.array([p["mu_b"], p["mu_s"]], float)
            alpha = np.array(
                [[p["alpha_bb"], p["alpha_bs"]], [p["alpha_sb"], p["alpha_ss"]]], float
            )
            beta = float(p["beta"])
            if s["name"] == "C1":
                sig_side = shuffled_sides(sig_side, int(s.get("seed", 1729)))
        else:
            raise ValueError(f"unknown strategy {s['name']}")
    return mode, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta


def _no_signal() -> tuple:
    return (NONE, np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(1), 1.0, 1,
            np.zeros(2), np.zeros((2, 2)), 1.0)  # fmt: skip


def _overlay_args(s: dict, day: str, cfg: dict, oracle=None) -> tuple:
    """v1 overlay arguments for run_overlay: signal inputs, c, d and K. C3 is B3 at zero
    latency.

    C2 is the B1 overlay with c = 1 and m = 0 on an oracle series (time, u, m) that the
    caller supplies, because the only code allowed to look ahead lives in tests/canary/
    (SPEC.md AC3.6). The engine never builds that series itself.
    """
    if s["name"] == "C2":
        if oracle is None:
            raise ValueError("C2 needs its oracle series: run it with tests/canary/run_c2.py")
        ts, u, m = oracle(day, cfg)
        if s.get("flip"):
            u = -u  # M4 diagnosis item 1: the oracle's sign reversed, exploratory
        return (
            EXTERNAL, 1.0, 0.0, 1.0, NORM_STEPS, ts, np.zeros(len(ts), np.int64), np.zeros(1),
            1.0, 1, np.zeros(2), np.zeros((2, 2)), 1.0, u, m, np.zeros((0, 3)),
        )  # fmt: skip
    if s["name"] == "B1":  # only with touch (M4 diagnosis): no signal, c = d = 0
        mode, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta = _no_signal()
        c, d, K = 0.0, 0.0, 1.0
    else:
        mode, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta = _signal_inputs(s, day)
        c, d, K = float(s["c"]), float(s["d"]), float(s["K"])
    return (
        mode, c, d, K, NORM_STEPS, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta,
        np.zeros(0), np.zeros(0), np.zeros((0, 3)),
    )  # fmt: skip


def _touch_args(s: dict, day: str, cfg: dict, oracle=None) -> tuple:
    """v2 arguments for run_touch after the common ones: skew, signal inputs, K, and the
    overlay's theta_u, k_ticks and theta_m (PREREGISTRATION.md section 4). B0 and B1 get
    infinite thresholds, so the overlay never acts. C2's series comes from tests/canary/,
    as in v1."""
    off = np.inf
    no_ext = (np.zeros(0), np.zeros(0))
    if s["name"] in ("B0", "B1", "F"):
        # F (fill-hold control, exploratory): B1 that withholds a side for hold_s after
        # each of our fills on it (strategies.touch.run_touch).
        hold_ns = int(round(float(s["hold_s"]) * 1e9)) if s["name"] == "F" else 0
        mode, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta = _no_signal()
        return (s["name"] != "B0", mode, 1.0, NORM_STEPS, sig_ts, sig_side, cum, tau,
                ofi_window, mu, alpha, beta, *no_ext, off, 0, off, np.zeros((0, 3)),
                hold_ns)  # fmt: skip
    if s["name"] == "C2":
        if oracle is None:
            raise ValueError("C2 needs its oracle series: run it with tests/canary/run_c2.py")
        ts, u, m = oracle(day, cfg, design="v2")
        mode, _, _, cum, tau, ofi_window, mu, alpha, beta = _no_signal()
        return (True, EXTERNAL, 1.0, NORM_STEPS, ts, np.zeros(len(ts), np.int64), cum, tau,
                ofi_window, mu, alpha, beta, u, m, 0.5, PULL, off, np.zeros((0, 3)), 0)  # fmt: skip
    if s["name"] in ("R", "RL"):
        # The rate (and for RL the number of pulled runs) is the realised value of the
        # strategy the control is for (C1, B3 or B2b) on this day, from a committed run;
        # the config carries it per day.
        start, end = utc_ns(day, cfg["quote_start"]), utc_ns(day, cfg["quote_end"])
        rate, step, seed = float(s["pull_rate"][day]), int(cfg["step_ns"]), int(s["seed"])
        if s["name"] == "R":
            ts, u, m = random_pulls(day, start, end, step, rate, seed)
        else:
            n = int(s["episodes"][day])
            ts, u, m = run_length_pulls(day, start, end, step, rate, n, seed)
        mode, _, _, cum, tau, ofi_window, mu, alpha, beta = _no_signal()
        k_ticks = PULL if s["k_ticks"] == "pull" else int(s["k_ticks"])
        return (True, EXTERNAL, 1.0, NORM_STEPS, ts, np.zeros(len(ts), np.int64), cum, tau,
                ofi_window, mu, alpha, beta, u, m, 0.5, k_ticks, off, np.zeros((0, 3)), 0)  # fmt: skip
    mode, sig_ts, sig_side, cum, tau, ofi_window, mu, alpha, beta = _signal_inputs(s, day)
    k_ticks = PULL if s["k_ticks"] == "pull" else int(s["k_ticks"])
    theta_m = float(s["theta_m"]) if s["magnitude"] else off
    return (True, mode, float(s["K"]), NORM_STEPS, sig_ts, sig_side, cum, tau, ofi_window,
            mu, alpha, beta, *no_ext, float(s["theta_u"]), k_ticks, theta_m,
            np.zeros((0, 3)), 0)  # fmt: skip


def build_backtest(day: str, queue: str, latency: str, maker_fee=0.0, taker_fee=0.0):
    venue = venue_for(day)
    # Paths, or arrays that _IN_MEMORY keeps alive: hftbacktest does not copy an array.
    asset = BacktestAsset().data(day_parts(day)).linear_asset(1.0)
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


def run_cell(
    cell: dict, cfg: dict, maker_fee_bps: float = 0.0, oracle=None
) -> tuple[dict, pl.DataFrame]:
    """One day of one strategy in one queue-model and latency cell. Returns (metrics row,
    fills with markouts). maker_fee_bps puts a fee into hftbacktest itself (AC2.3 test);
    oracle is C2's series builder (see _overlay_args)."""
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
        if s.get("design") == "v2":
            run_touch(hbt, *common, start, end, step, steps, fills, out,
                      *_touch_args(s, day, cfg, oracle))  # fmt: skip
        elif s["name"] == "B0":
            run_b0(hbt, int(s["h"]), *common, start, end, step, steps, fills, out)
        elif s["name"] == "B1" and not s.get("touch"):
            window = int(float(s["window_s"]) * 1e9 / step)
            run_b1(hbt, float(s["gamma"]), window, int(s.get("update_every", 50)), *common,
                   start, end, step, steps, fills, out)  # fmt: skip
        else:
            window = int(float(s["window_s"]) * 1e9 / step)
            run_overlay(hbt, float(s["gamma"]), window, int(s.get("update_every", 50)), *common,
                        start, end, step, steps, fills, out, *_overlay_args(s, day, cfg, oracle),
                        bool(s.get("touch", False)))  # fmt: skip
    finally:
        hbt.close()
    wall = time.perf_counter() - t0
    steps, fills = steps[: int(out[0])], fills[: int(out[12])]
    # hftbacktest lists orders in hash-map order, which differs between processes; sorted
    # fills make every sum below, and so every metric, the same in every run.
    fills = np.sort(fills, order=["local_ts", "order_id"])
    fee_levels = {
        name: venue["maker_fee_bps"] if f == "venue" else float(f)
        for name, f in cfg["fee_levels_bps"].items()
    }
    m = day_metrics(
        fills, steps, mark_mid=out[4], order_qty=out[5], fee_levels_bps=fee_levels,
        funding_ns=[utc_ns(day, "08:00:00"), utc_ns(day, "16:00:00")],
    )  # fmt: skip
    mk = markouts(fills, steps)
    if "select_from" in cfg:
        # Selection window (Q45): every B0 and B1 candidate is scored from the latest first
        # quote among them, as sel_* columns beside the full-day metrics.
        w = window_metrics(fills, steps, out[4], utc_ns(day, cfg["select_from"]))
        sel = {f"sel_{k}": v for k, v in w.items()}
    else:
        sel = {}
    row = {
        "day": day,
        "strategy": s["name"],
        # Tells apart two entries of one strategy, such as C4 at x10 and x0.1.
        "label": s.get("label", s["name"]),
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
        "no_print_fill_share": no_print_share(fills, opposite_prints(day), venue["tick_size"]),
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
        **sel,
        # Diagnostics (M4 diagnosis, exploratory): not section 6 metrics.
        **{k: (json.dumps(v) if k == "hourly_quotes" else v)
           for k, v in quote_metrics(fills, steps).items()},
    }  # fmt: skip
    fills_df = pl.DataFrame({name: fills[name] for name in FILL_DTYPE.names} | mk)
    return row, fills_df


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


def fills_name(strategy: dict, cell: dict, repeated: bool) -> str:
    """fills_<label>_<queue>_<latency>_<day>, plus a short hash of the parameters when the
    config has several entries with one label (a selection grid), so none overwrites another."""
    label = strategy.get("label", strategy["name"])
    name = f"{label}_{cell['queue']}_{cell['latency']}_{cell['day']}"
    if repeated:
        h = hashlib.sha256(json.dumps(strategy, sort_keys=True).encode()).hexdigest()[:8]
        name += f"_{h}"
    return name


def run_config(cfg_path: Path, oracle=None, after_day=None) -> Path:
    """Run every cell of a committed config. after_day(day), if given, runs once a day's
    last cell is done and before its converted parts may be evicted, so work that needs the
    parts (the M1 report) shares the run's conversion instead of making its own."""
    rel = Path(cfg_path).resolve().relative_to(ROOT).as_posix()
    if not _git("ls-files", "--", rel).strip():
        raise SystemExit(f"{rel} is not tracked by git; commit the config first")
    if _git("status", "--porcelain").strip():
        raise SystemExit("working tree has changes; results must map to a commit")
    cfg = yaml.safe_load(Path(cfg_path).read_text())
    if oracle is None and any(s["name"] == "C2" for s in cfg["strategies"]):
        raise SystemExit("C2 needs its oracle series: run it with tests/canary/run_c2.py")
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
    cells = expand(cfg)
    repeated = Counter(s.get("label", s["name"]) for s in cfg["strategies"])
    for n, cell in enumerate(cells):
        row, fills = run_cell(cell, cfg, oracle=oracle)
        name = fills_name(cell["strategy"], cell, repeated[row["label"]] > 1)
        fills.write_parquet(out_dir / f"fills_{name}.parquet")
        rows.append(row)
        print(
            f"{name}: {row['fills']} fills, BEF {row['break_even_fee_bps']:.3f} bp, {row['wall_seconds']} s"
        )
        if n + 1 == len(cells) or cells[n + 1]["day"] != cell["day"]:
            # expand() is day-major: the day's last cell is done, so its parts may go.
            from toxic_flow.data.convert import evict_converted

            if after_day is not None:
                after_day(cell["day"])
            evict_converted(cell["day"])
    pl.DataFrame(rows).write_parquet(out_dir / "metrics.parquet")
    meta["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return out_dir


if __name__ == "__main__":
    print(run_config(Path(sys.argv[1])))
