#!/usr/bin/env python3
"""Every pre-test number the paper prints, from committed results/ and the committed files
built from them, into paper/pre_test.json. Training and validation days only: no test-day
file is read. The paper's test-day numbers come from results/summary.json instead.

Usage: uv run python paper/pre_test.py   (make paper runs it before the build)

Each value is a string, already formatted, so the build prints it as it is. Keys start
with pre_ so a test-day key can never be filled from here.
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from m4_v2 import kept  # noqa: E402

from toxic_flow.data.split_lock import load_splits  # noqa: E402
from toxic_flow.engine.configs import quote_hours  # noqa: E402
from toxic_flow.eval import analysis  # noqa: E402

OUT = ROOT / "paper" / "pre_test.json"
PRIMARY = ("risk_averse", "high")
# Committed runs, by the config each must come from (checked against meta.json).
RUNS = {
    "v2_train": "4db60c584c71",
    "v2_tune_val_a": "0bd4181a312a",
    "v2_tune_val_b": "9e93e4415b6b",
    "v2_canaries_val": "5d27bc8ae820",
    "v2_mde_train": "58c46cc49981",
    "v2_random_pulls_val": "c274b2def28e",
    "v2_run_length_val": "7ac2bbe74a19",
    "v2_fill_hold_train": "83bb2b991997",
    "v2_fill_hold_val": "fb21705e1269",
    "canaries_val_draft": "9eaa1b3d693c",  # v1 canaries (GLFT base)
    "diag_train_touch": "a582f2864e78",  # v1 B1 and the touch base, training days
    "diag_val": "4de702fe5d20",  # v1 B1 on validation days
    "train_select_window": "ccbf1a18e770",  # GLFT grid, training days
    "train_chosen_window": "633a29217f4b",  # chosen GLFT in all 8 cells
}


def run(config: str) -> pl.DataFrame:
    h = RUNS[config]
    meta = json.loads((ROOT / "results" / h / "meta.json").read_text())
    if meta["config"] != f"configs/runs/{config}.yaml":
        raise SystemExit(f"results/{h} is not {config}")
    return pl.read_parquet(ROOT / "results" / h / "metrics.parquet")


def primary(m: pl.DataFrame) -> pl.DataFrame:
    return m.filter((pl.col("queue") == PRIMARY[0]) & (pl.col("latency") == PRIMARY[1]))


def num(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"


def ci(c) -> str:
    return f"[{num(c[0])}, {num(c[1])}]"


def put_compare(out: dict, key: str, c: dict) -> None:
    """mean, bootstrap interval and days above 0 of one paired comparison."""
    out[f"{key}_mean"] = num(c["mean"])
    out[f"{key}_ci"] = ci(c["bootstrap_ci"])
    out[f"{key}_t_ci"] = ci(c["t_ci"])
    out[f"{key}_pos"] = f"{c['n_positive']} of {c['n']}"


def split_counts(out: dict) -> None:
    splits = load_splits()  # day lists only; no test-day data is read
    out["pre_n_train"], out["pre_n_val"] = str(len(kept("train"))), str(len(kept("val")))
    out["pre_n_test"] = str(len(splits["test"]))


def venue(out: dict) -> None:
    from toxic_flow.data.venue import venue_for

    days = kept("train") + kept("val")  # configs/venue.yaml only; no market data
    specs = {
        k: {venue_for(d)[k] for d in days} for k in ("tick_size", "maker_fee_bps", "min_notional")
    }
    for k, v in specs.items():
        if len(v) != 1:
            raise SystemExit(f"{k} differs across training and validation days: {v}")
    out["pre_tick"] = f"{specs['tick_size'].pop():g}"
    out["pre_maker_fee"] = f"{specs['maker_fee_bps'].pop():g}"
    out["pre_min_notional"] = f"{specs['min_notional'].pop():g}"


def hawkes(out: dict) -> None:
    c = json.loads((ROOT / "docs" / "signals" / "train_constants.json").read_text())["hawkes"]
    out["pre_hawkes_events"] = f"{c['n_events']:,}"
    out["pre_hawkes_br"] = num(c["branching_ratio"], 3)
    for k in ("mu_b", "mu_s", "alpha_bb", "alpha_bs", "alpha_sb", "alpha_ss"):
        out[f"pre_hawkes_{k}"] = num(c["params"][k], 3)
    out["pre_hawkes_beta"] = num(c["params"]["beta"], 2)
    out["pre_hawkes_memory_ms"] = num(1000 / c["params"]["beta"], 0)  # 1 / beta


def selected() -> dict:
    return yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())


def thresholds(out: dict) -> None:
    """theta_u at each overlay's selected setting, from the training-day file."""
    th = json.loads((ROOT / "docs" / "signals" / "train_thresholds.json").read_text())["signals"]
    sel = selected()
    keys = {"b3": ("B3_hawkes", sel["B3"]),
            "b2b": (f"B2b_ewma_{sel['B2b']['tau_s']:g}s", sel["B2b"]),
            "b2": (f"B2_ofi_{sel['B2']['ofi_window_s']:g}s", sel["B2"])}  # fmt: skip
    for k, (name, s) in keys.items():
        out[f"pre_theta_{k}"] = num(th[name]["theta_u"][f"{s['p']:g}"])


def mde(out: dict) -> None:
    mc = run("v2_canaries_val")
    # The kept test days, as scripts/analyse.py mde counts them; all 16 before the download.
    x = analysis.mde_inputs(run("v2_mde_train"), mc, len(kept("test")))
    out["pre_s_train"], out["pre_s_val"] = num(x["s_train_bp"]), num(x["s_val_bp"])
    out["pre_s"], out["pre_mde"] = num(x["s_bp"]), num(x["mde_bp"])
    out["pre_3mde"] = num(3 * x["mde_bp"])


def v1(out: dict) -> None:
    put_compare(out, "pre_v1_c2_b1", analysis.compare(run("canaries_val_draft"), "C2", "B1"))
    for key, config in (("train", "diag_train_touch"), ("val", "diag_val")):
        b1 = primary(run(config)).filter(pl.col("label") == "B1")
        out[f"pre_v1_ticks_{key}"] = num(float(b1["median_bid_dist_ticks"].mean()), 0)
        out[f"pre_v1_fills_{key}"] = num(float(b1["fills"].mean()), 0)


def touch(out: dict) -> None:
    m = run("v2_train")
    b1 = primary(m).filter(pl.col("strategy") == "B1")
    out["pre_b1_fills"] = f"{b1['fills'].mean():,.0f}"
    out["pre_b1_bef"] = num(float(b1["break_even_fee_bps"].mean()), 3)
    out["pre_b1_mk1"] = num(float(b1["mean_markout_1s_bps"].mean()), 3)
    out["pre_b1_mk60"] = num(float(b1["mean_markout_60s_bps"].mean()), 3)
    cells = m.group_by("strategy", "queue", "latency").agg(pl.col("break_even_fee_bps").mean())
    out["pre_base_bef_lo"] = num(float(cells["break_even_fee_bps"].min()), 2)
    out["pre_base_bef_hi"] = num(float(cells["break_even_fee_bps"].max()), 2)
    fills = m.group_by("strategy", "queue", "latency").agg(pl.col("fills").mean())["fills"]
    out["pre_base_fills_lo"] = f"{fills.min():,.0f}"
    out["pre_base_fills_hi"] = f"{fills.max():,.0f}"


def signals(out: dict) -> None:
    d = json.loads((ROOT / "docs" / "exploratory" / "signal_information.json").read_text())
    for split in ("train", "val"):
        t = d["splits"][split]["table"]
        for name, key in (("B2_ofi_1s", "ofi1"), ("B2b_ewma_1s", "ewma1"), ("B2b_ewma_5s", "ewma5"),
                          ("B3_hawkes", "hawkes"), ("C4_x0.1", "slow")):  # fmt: skip
            out[f"pre_sig_{split}_{key}_u1"] = num(t[f"{name}|1"]["u"]["mean"], 3)
            out[f"pre_sig_{split}_{key}_m1"] = num(t[f"{name}|1"]["m"]["mean"], 3)
        h = d["splits"][split]["hawkes_minus_ewma_u"]
        for tau in (1, 5):
            for hz in (1, 5):
                x = h[f"B3_minus_B2b_{tau}s|{hz}"]
                out[f"pre_sig_{split}_h_e{tau}_{hz}"] = num(x["mean"], 3)
                out[f"pre_sig_{split}_h_e{tau}_{hz}_ci"] = (
                    f"[{num(x['ci'][0], 3)}, {num(x['ci'][1], 3)}]"
                )
                out[f"pre_sig_{split}_h_e{tau}_{hz}_pos"] = f"{x['days_above_0']} of {x['days']}"


def validation(out: dict) -> None:
    sel = selected()
    out["pre_sel_b2"] = f"W = {sel['B2']['ofi_window_s']:g} s at p = {sel['B2']['p']:.0%}"
    out["pre_sel_b2b"] = f"tau = {sel['B2b']['tau_s']:g} s at p = {sel['B2b']['p']:.0%}"
    out["pre_sel_b3"] = f"p = {sel['B3']['p']:.0%}"
    mc = run("v2_canaries_val")
    for a, b in (("C2", "B1"), ("C1", "B1"), ("B3", "B1"), ("B2b", "B1"), ("B3", "B2b"),
                 ("C4_x0.1", "B3"), ("C4_x10", "B3")):  # fmt: skip
        key = f"pre_val_{a}_{b}".lower().replace(".", "")
        put_compare(out, key, analysis.compare(mc, a, b))
    c2 = primary(mc).filter(pl.col("label") == "C2")
    out["pre_val_c2_bef"] = num(float(c2["break_even_fee_bps"].mean()), 2)
    shares = primary(mc).group_by("label").agg(pl.col("toxic_share").mean())
    share = dict(zip(shares["label"], shares["toxic_share"], strict=True))
    out["pre_val_share_c1"] = f"{share['C1']:.1%}"
    out["pre_val_share_b3"] = f"{share['B3']:.1%}"
    out["pre_val_share_b2b"] = f"{share['B2b']:.1%}"
    m = analysis.with_seed_means(run("v2_random_pulls_val"))
    for a, b in (("C1", "R1"), ("R1", "B1"), ("B3", "R_B3"), ("B2b", "R_B2b")):
        put_compare(out, f"pre_rp_{a}_{b}".lower(), analysis.compare(m, a, b))
    hours = quote_hours()
    for lab in ("C1", "R1", "B3", "R_B3", "B2b", "R_B2b"):
        ep = m.filter(pl.col("label") == lab)["toxic_episodes"].mean() / hours
        out[f"pre_rp_runs_{lab.lower()}"] = f"{ep:,.0f}"
    # RL: random pulls matched on the number of pulled runs as well (exploratory).
    rl = analysis.with_seed_means(run("v2_run_length_val"))
    for a, b in (("B3", "RL_B3"), ("B2b", "RL_B2b")):
        put_compare(out, f"pre_rl_{a}_{b}".lower(), analysis.compare(rl, a, b))
    # F: no rejoining the side just filled, hold chosen on training days (exploratory).
    f = pl.concat([run("v2_fill_hold_val"), rl.filter(pl.col("strategy") == "RL")],
                  how="diagonal_relaxed")  # fmt: skip
    for a, b in (("B3", "F"), ("F", "RL_B3")):
        put_compare(out, f"pre_f_{a}_{b}".lower(), analysis.compare(f, a, b))
    hold = {
        json.loads(x)["hold_s"]
        for x in run("v2_fill_hold_val").filter(pl.col("strategy") == "F")["params"]
    }
    (out["pre_f_hold"],) = (f"{h:g}" for h in hold)
    # F's pull share against B3's: matched on the training days by the rule, not on these.
    train_f = run("v2_fill_hold_train").filter(pl.col("label") == f"F_h{out['pre_f_hold']}")
    train_b3 = primary(run("v2_mde_train")).filter(pl.col("label") == "B3")
    val = primary(run("v2_fill_hold_val"))
    for key, rows in (("train_f", train_f), ("train_b3", train_b3),
                      ("val_f", val.filter(pl.col("label") == "F")),
                      ("val_b3", val.filter(pl.col("label") == "B3"))):  # fmt: skip
        out[f"pre_f_share_{key}"] = num(float(rows["toxic_share"].mean()))


def matched_p(out: dict) -> None:
    from m4_v2 import matched_pairs, tune_runs

    mt, _ = tune_runs([ROOT / "results" / RUNS[c] for c in ("v2_tune_val_a", "v2_tune_val_b")])
    for p, both in matched_pairs(mt, selected()).items():
        put_compare(out, f"pre_mp_{round(p * 100)}", analysis.compare(both, "B3", "B2b"))


def glft(out: dict) -> None:
    g = primary(run("train_select_window")).filter(pl.col("strategy") == "B1")
    g = g.with_columns(
        gamma=pl.col("params").map_elements(
            lambda s: json.loads(s)["gamma"], return_dtype=pl.Float64
        )
    )
    per = g.group_by("params", "gamma").agg(
        bef=pl.col("break_even_fee_bps").mean(), fills=pl.col("fills").median()
    )
    by = per.group_by("gamma").agg(pl.col("bef").max(), pl.col("fills").median())
    row = {r["gamma"]: r for r in by.iter_rows(named=True)}
    c = primary(run("train_chosen_window")).filter(pl.col("strategy") == "B1")
    lo = min(row)
    chosen = json.loads(c["params"][0])["gamma"]  # the v1 choice, gamma 0.4
    out["pre_glft_gamma_lo"], out["pre_glft_gamma_chosen"] = f"{lo:g}", f"{chosen:g}"
    out["pre_glft_bef_low_gamma"] = num(row[lo]["bef"], 2)
    out["pre_glft_bef_gamma04"] = num(row[chosen]["bef"], 2)
    out["pre_glft_fills_low_gamma"] = f"{row[lo]['fills']:,.0f}"
    out["pre_glft_fills_gamma04"] = f"{row[chosen]['fills']:,.0f}"
    out["pre_glft_chosen_bef"] = num(float(c["break_even_fee_bps"].mean()), 3)
    out["pre_glft_chosen_fills"] = f"{c['fills'].mean():,.0f}"
    xs, ys = [], []
    for config in ("diag_train_touch", "diag_val"):
        b1 = run(config).filter(pl.col("label") == "B1")
        xs += b1["mark_mid"].to_list()
        ys += b1["median_bid_dist_ticks"].to_list()
    out["pre_glft_corr"] = num(float(np.corrcoef(xs, ys)[0, 1]), 2)
    out["pre_glft_days"] = str(len(xs))
    touch = primary(run("v2_train")).filter(pl.col("strategy") == "B1")["fills"].mean()
    out["pre_glft_fill_ratio"] = num(touch / c["fills"].mean(), 0)
    mids = {}
    for config in ("diag_train_touch", "diag_val"):
        b1 = primary(run(config)).filter(pl.col("label") == "B1")
        mids |= dict(zip(b1["day"], b1["mark_mid"], strict=True))
    val = [v for d, v in mids.items() if d in kept("val")]
    out["pre_mid_first_train"] = f"{mids[min(mids)]:,.0f}"
    out["pre_mid_val_lo"], out["pre_mid_val_hi"] = f"{min(val):,.0f}", f"{max(val):,.0f}"


def build() -> dict:
    out: dict = {"note": "Pre-test numbers for the paper (paper/pre_test.py); training and "
                 "validation days only."}  # fmt: skip
    for step in (split_counts, venue, hawkes, thresholds, mde, v1, touch, signals, validation,
                 matched_p, glft):  # fmt: skip
        step(out)
    return out


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
