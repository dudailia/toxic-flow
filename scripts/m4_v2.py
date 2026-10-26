#!/usr/bin/env python3
"""M4 for the v2 design, from results/ only (PREREGISTRATION.md sections 4, 9 and 10).

  uv run python scripts/m4_v2.py select --tune results/<v2_tune_val_a> results/<v2_tune_val_b>
      Section 4 rule on the validation days, primary cell. Writes docs/M4_v2_selected.yaml,
      which make_v2_configs.py reads for the canary and training runs. Not
      configs/selected.yaml and not PREREGISTRATION.md: those wait for Ilia.
  uv run python scripts/m4_v2.py report --train-b results/<v2_train> \
      --tune results/<a> results/<b> --canaries results/<v2_canaries_val> --mde results/<v2_mde_train>
      Writes docs/M4_v2_draft.md: B0 and B1 on the training days in all 8 cells, the tuning
      tables, the MDE (section 9) and the canaries (section 10).
  uv run python scripts/m4_v2.py random --random results/<v2_random_pulls_val> \
      --canaries results/<v2_canaries_val> --tune results/<a> results/<b>
      Writes the section "Random-pull controls" at the end of docs/M4_v2_draft.md (replacing
      it if present): C1 against R1 (the section 10 rule as revised on 2026-10-26), and the
      exploratory comparisons: B3 and B2b against random pulls at their own rates, and B3
      against B2b at each matched p from the tuning runs.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from toxic_flow.data.exclusions import excluded_days
from toxic_flow.data.split_lock import load_splits
from toxic_flow.eval import analysis
from toxic_flow.eval.analysis import BEF
from toxic_flow.eval.select import PRIMARY, candidate_table, select

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ROOT / "docs" / "M4_v2_selected.yaml"
THRESHOLDS = ROOT / "docs" / "signals" / "train_thresholds.json"
OVERLAYS = ("B2", "B2b", "B3")
KEEP = ("p", "k_ticks", "magnitude", "ofi_window_s", "tau_s")


def kept(split: str) -> list[str]:
    days = load_splits()[split]
    return sorted(d for d in days if d not in excluded_days(days))


def load(run_dirs: list[Path], configs: list[str], split: str) -> tuple[pl.DataFrame, list[dict]]:
    """Runs' metrics together, refused unless they are the named configs and cover the kept
    days of the split between them."""
    ms, metas = [], []
    for d, cfg in zip(run_dirs, configs, strict=True):
        meta = json.loads((d / "meta.json").read_text())
        if meta["config"] != f"configs/runs/{cfg}.yaml":
            raise SystemExit(f"{d} is not {cfg}")
        ms.append(pl.read_parquet(d / "metrics.parquet"))
        metas.append(meta)
    m = pl.concat(ms, how="diagonal_relaxed")
    if sorted(set(m["day"])) != kept(split):
        raise SystemExit(f"{[str(d) for d in run_dirs]} do not cover the kept {split} days")
    return m, metas


def fmt(x, nd=4) -> str:
    return "none" if x is None or not np.isfinite(x) else f"{x:.{nd}f}"


def ci(c) -> str:
    return f"[{fmt(c[0])}, {fmt(c[1])}]"


def short(params: str | dict) -> str:
    p = json.loads(params) if isinstance(params, str) else params
    return json.dumps({k: p[k] for k in KEEP if k in p})


CMP_HEAD = ["| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |",
            "|---|---|---|---|---|---|---|"]  # fmt: skip


def cmp_row(name: str, c: dict) -> str:
    return (f"| {name} | {c['n']} | {fmt(c['mean'])} | {ci(c['bootstrap_ci'])} | {ci(c['t_ci'])} "
            f"| {c['n_positive']} | {', '.join(c['dropped']) or 'none'} |")  # fmt: skip


def tune_runs(paths: list[Path]):
    return load(paths, ["v2_tune_val_a", "v2_tune_val_b"], "val")


def cmd_select(tune: list[Path]) -> None:
    m, metas = tune_runs(tune)
    out = {
        "draft": "v2 M4 from runs " + ", ".join(x["config_hash"] for x in metas) + ", not approved"
    }
    for name in OVERLAYS:
        pick = select(candidate_table(m, name, kept("val")), name)
        out[name] = {k: v for k, v in pick["params"].items() if k in KEEP}
    SELECTED.write_text(
        "# v2 overlay choice by the section 4 rule (scripts/m4_v2.py select), for Ilia's review.\n"
        "# Not configs/selected.yaml; make_v2_configs.py reads it for the canary and s runs.\n"
        + yaml.safe_dump(out, sort_keys=False)
    )
    print(SELECTED, json.dumps({k: out[k] for k in OVERLAYS}))


def base_section(train: Path) -> list[str]:
    m, (meta,) = load([train], ["v2_train"], "train")
    L = ["## B0 and B1 on the training days, all 8 cells (section 4, v2)", "",
         f"Run {meta['config_hash']} (configs/runs/v2_train.yaml, commit {meta['commit'][:7]}), "
         f"{len(kept('train'))} training days. Means over days; markouts per fill in our favour.", "",
         "| Strategy | Queue model | Latency | Fills a day | Mean daily BEF bp | Pooled BEF bp | Markout 1 s bp | Markout 60 s bp | Both sides resting |",
         "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for (s, q, lat), g in m.group_by(["strategy", "queue", "latency"], maintain_order=True):
        pooled = 1e4 * g["gross_pnl"].sum() / g["traded_notional"].sum()
        L.append(f"| {s} | {q} | {lat} | {g['fills'].mean():.0f} | {fmt(g['break_even_fee_bps'].mean())} | "
                 f"{fmt(pooled)} | {fmt(g['mean_markout_1s_bps'].mean())} | {fmt(g['mean_markout_60s_bps'].mean())} | "
                 f"{fmt(g['quote_presence'].mean(), 3)} |")  # fmt: skip
    return L


def tuning_section(m: pl.DataFrame, metas: list[dict]) -> list[str]:
    days = kept("val")
    L = ["## Overlay tuning on the validation days (section 4, v2)", "",
         "Runs " + ", ".join(f"{x['config_hash']} ({x['config']}, commit {x['commit'][:7]})" for x in metas)
         + f", primary cell {PRIMARY[0]} / {PRIMARY[1]}, {len(days)} days: {', '.join(days)}. Rule: "
         "highest mean daily break-even fee; ties to the smaller p, then K (1, 5, pull), then the "
         "magnitude rule off, then the shorter window or decay. Toxic share: the realised share of "
         "quoting steps with a side marked toxic on these days, against p from the training days.",
         ]  # fmt: skip
    for name in OVERLAYS:
        table = candidate_table(m, name, days)
        pick = select(table, name)
        r = m.filter((pl.col("strategy") == name) & (pl.col("queue") == PRIMARY[0])
                     & (pl.col("latency") == PRIMARY[1]) & pl.col("day").is_in(days))  # fmt: skip
        extra = r.group_by("params").agg(
            pooled=1e4 * pl.col("gross_pnl").sum() / pl.col("traded_notional").sum(),
            toxic=pl.col("toxic_share").mean(), mk1=pl.col("mean_markout_1s_bps").mean(),
        )  # fmt: skip
        table = table.join(extra, on="params").sort("mean_bef_bps", descending=True)
        L += ["", f"### {name}", "",
              "| Candidate | Mean daily BEF bp | Pooled BEF bp | Median daily fills | Markout 1 s bp | Toxic share | Days without fills |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
        for x in table.iter_rows(named=True):
            L.append(f"| {short(x['params'])} | {fmt(x['mean_bef_bps'])} | {fmt(x['pooled'])} | "
                     f"{x['median_fills']:.0f} | {fmt(x['mk1'])} | {fmt(x['toxic'], 3)} | {x['zero_fill_days']} |")  # fmt: skip
        L += ["", f"Choice: {short(pick['params'])}, mean daily BEF {fmt(pick['mean_bef_bps'])} bp"
              + (f", {pick['tied']} candidates tied at the top." if pick["tied"] > 1 else ".")]  # fmt: skip
    return L


def threshold_lines() -> list[str]:
    th = json.loads(THRESHOLDS.read_text())
    L = ["## Thresholds from the training days (section 5, v2)", "",
         "docs/signals/train_thresholds.json (scripts/fit_thresholds.py). Pooled share of training-day",
         "steps above each threshold in brackets.", "",
         "| Signal setting | theta_u at p 5% | 10% | 25% | 50% | theta_m |", "|---|---|---|---|---|---|"]  # fmt: skip
    for name, s in th["signals"].items():
        cells = [
            f"{fmt(s['theta_u'][p])} ({s['share_above'][p]:.3f})"
            for p in ("0.05", "0.1", "0.25", "0.5")
        ]
        L.append(
            f"| {name} | "
            + " | ".join(cells)
            + f" | {fmt(s['theta_m'])} ({s['share_m_above']:.3f}) |"
        )
    return L


def cmd_report(train_b: Path, tune: list[Path], canaries: Path, mde_run: Path) -> None:
    mt, metas_t = tune_runs(tune)
    mc, (meta_c,) = load([canaries], ["v2_canaries_val"], "val")
    mtr, (meta_tr,) = load([mde_run], ["v2_mde_train"], "train")
    n_test = len(load_splits()["test"])  # the count only; no test-day data is read
    mde = analysis.mde_inputs(mtr, mc, n_test)
    can = analysis.canaries(mc, mde["mde_bp"])
    L = ["# M4 v2: overlay tuning, canaries and MDE (draft for Ilia's review)", "",
         "Draft. Nothing here is written into PREREGISTRATION.md or configs/selected.yaml; every",
         "[TBD] there is unchanged. All numbers come from the runs named below, through",
         "scripts/m4_v2.py. Training and validation days only; no test day was loaded.", "",
         *base_section(train_b), "", *threshold_lines(), "", *tuning_section(mt, metas_t), "",
         "## Minimum detectable effect (section 9)", "",
         "s is the larger of the standard deviations of D_i = BEF_B3 - BEF_B2b with the selected",
         f"settings: on the training days (run {meta_tr['config_hash']}) and on the validation days",
         f"(run {meta_c['config_hash']}). n = {n_test} test days.", "",
         "| Quantity | Value |", "|---|---|",
         f"| s on training days, bp | {fmt(mde['s_train_bp'])} |",
         f"| s on validation days, bp | {fmt(mde['s_val_bp'])} |",
         f"| s, bp | {fmt(mde['s_bp'])} |",
         f"| MDE = 0.70 s, bp | {fmt(mde['mde_bp'])} |",
         f"| 3 x MDE (C2 threshold), bp | {fmt(3 * mde['mde_bp'])} |", "",
         "## Canaries on the validation days (section 10, v2)", "",
         f"Run {meta_c['config_hash']} ({meta_c['config']}, commit {meta_c['commit'][:7]}), primary cell;",
         "C3 is B3 at zero latency in the risk-averse queue model.", "", *CMP_HEAD]  # fmt: skip
    rows = []
    if "C1" in can:
        rows.append(("C1 - B1 (pass: interval includes 0)", can["C1"]))
        if "vs_B3" in can["C1"]:
            rows.append(("C1 - B3 (descriptive)", can["C1"]["vs_B3"]))
    if "C2" in can:
        rows.append(("C2 - B1 (pass: mean above 3 x MDE)", can["C2"]))
    for v in sorted(k for k in can.get("C4", {}) if k.startswith("C4")):
        rows.append((f"{v} - B3", can["C4"][v]))
    rows += [("B3 - B1 (descriptive, H3 on validation days)", analysis.compare(mc, "B3", "B1")),
             ("B2b - B1 (descriptive, H4 on validation days)", analysis.compare(mc, "B2b", "B1")),
             ("B3 - B2b (descriptive, H1's statistic on validation days)", analysis.compare(mc, "B3", "B2b"))]  # fmt: skip
    L += [cmp_row(n, c) for n, c in rows]
    verdict = {True: "passes", False: "fails", None: "no verdict"}
    c3 = can.get("C3", {})
    prim = mc.filter((pl.col("queue") == PRIMARY[0]) & (pl.col("latency") == PRIMARY[1]))
    L += [
        "",
        "| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Toxic share |",
        "|---|---|---|---|---|",
    ]
    for lab in ("B1", "B2b", "B3", "C1", "C2", "C4_x10", "C4_x0.1"):
        g = prim.filter(pl.col("label") == lab)
        if g.height:
            L.append(f"| {lab} | {g['fills'].mean():.0f} | {fmt(g['break_even_fee_bps'].mean())} | "
                     f"{fmt(g['mean_markout_1s_bps'].mean())} | {fmt(g['toxic_share'].mean(), 3)} |")  # fmt: skip
    L += ["",
          f"- AC4.2, C2 beats B1 by more than 3 x MDE: {verdict[can['C2']['pass']] if 'C2' in can else 'not run'}.",
          f"- AC4.3, the C1 interval against B1 includes 0: {verdict[can['C1']['pass']] if 'C1' in can else 'not run'}.",
          "- C3, mean BEF of B3 by latency, bp: "
          + ", ".join(f"{k} {fmt(v)}" for k, v in c3.get("mean_bef_bp", {}).items())
          + f"; flag (a non-zero latency above zero latency): {c3.get('flag')}.",
          f"- C4, matches B3 within the interval: {can.get('C4', {}).get('matches_b3')}.",
          "", f"Statement from eval/analysis.canaries: {can['statement']}"]  # fmt: skip
    out = ROOT / "docs" / "M4_v2_draft.md"
    out.write_text("\n".join(L) + "\n")
    print(out)


RANDOM_HEAD = (
    "## Random-pull controls (section 10, C1 rule revised 2026-10-26; exploratory comparisons)"
)
REPRO = ("B1", "C1", "B3", "B2b")


def reproduced(m: pl.DataFrame, mc: pl.DataFrame) -> str:
    """Whether the random-pull run's B1, C1, B3 and B2b equal the canary run's, day by day."""
    cols = ["day", "label", "fills", "break_even_fee_bps"]
    a = m.filter(pl.col("label").is_in(REPRO)).select(cols)
    b = mc.filter(pl.col("label").is_in(REPRO) & (pl.col("latency") == PRIMARY[1])).select(cols)
    j = a.join(b, on=["day", "label"], suffix="_c")
    same = j.height == a.height == 4 * len(kept("val")) and (j["fills"] == j["fills_c"]).all()
    diff = float((j["break_even_fee_bps"] - j["break_even_fee_bps_c"]).abs().max())
    return (f"identical fills on every day, largest BEF difference {diff:.1e} bp" if same
            else f"NOT reproduced: {j.height} of {a.height} rows matched, largest BEF difference {diff:.1e} bp")  # fmt: skip


def matched_p(mt: pl.DataFrame, selected: dict) -> list[str]:
    """B3 against B2b at each p, both at B2b's selected decay and the selected K and
    magnitude rule (the same for both), from the tuning runs. Exploratory."""
    k, mg, tau = selected["B3"]["k_ticks"], selected["B3"]["magnitude"], selected["B2b"]["tau_s"]
    if (selected["B2b"]["k_ticks"], selected["B2b"]["magnitude"]) != (k, mg):
        raise SystemExit("B3 and B2b differ in K or the magnitude rule; matched p is not defined")
    prim = mt.filter((pl.col("queue") == PRIMARY[0]) & (pl.col("latency") == PRIMARY[1]))
    L = [f"Tuning runs, primary cell; K {k}, magnitude rule {'on' if mg else 'off'}, B2b at tau {tau:g} s.", "",
         "| p | B3 - B2b mean bp | Bootstrap 95% | t 95% | Days > 0 | B3 BEF bp | B2b BEF bp | B3 toxic share | B2b toxic share |",
         "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for p in (0.05, 0.10, 0.25, 0.50):
        rows = []
        for name, extra in (("B3", {}), ("B2b", {"tau_s": tau})):
            want = {"p": p, "k_ticks": k, "magnitude": mg, **extra}
            r = prim.filter(pl.col("strategy") == name).filter(
                pl.col("params").map_elements(
                    lambda s, w=want: all(json.loads(s).get(a) == v for a, v in w.items()),
                    return_dtype=pl.Boolean,
                )
            )
            if r["params"].n_unique() != 1:
                raise SystemExit(f"{name} at p {p}: {r['params'].n_unique()} settings")
            rows.append(r.with_columns(label=pl.lit(name)))
        both = pl.concat(rows, how="diagonal_relaxed")
        c = analysis.compare(both, "B3", "B2b")
        g = {n: both.filter(pl.col("label") == n) for n in ("B3", "B2b")}
        L.append(f"| {p:g} | {fmt(c['mean'])} | {ci(c['bootstrap_ci'])} | {ci(c['t_ci'])} | {c['n_positive']} | "
                 f"{fmt(g['B3'][BEF].mean())} | {fmt(g['B2b'][BEF].mean())} | "
                 f"{fmt(g['B3']['toxic_share'].mean(), 3)} | {fmt(g['B2b']['toxic_share'].mean(), 3)} |")  # fmt: skip
    return L


def cmd_random(random: Path, canaries: Path, tune: list[Path]) -> None:
    mr, (meta,) = load([random], ["v2_random_pulls_val"], "val")
    mc, _ = load([canaries], ["v2_canaries_val"], "val")
    mt, metas_t = tune_runs(tune)
    selected = yaml.safe_load(SELECTED.read_text())
    m = analysis.with_seed_means(mr)
    can = analysis.canaries(m, mde_bp=float("nan"))
    c1 = can["C1"]
    hours = 23 + 59 / 60 - 0.5  # quoting window, 00:30 to 23:59 UTC
    L = [RANDOM_HEAD, "",
         f"Run {meta['config_hash']} ({meta['config']}, commit {meta['commit'][:7]}), primary cell, "
         f"{len(kept('val'))} validation days. R is B1 that marks a side toxic at each 100 ms step with",
         "probability r and pulls it, the side chosen at random; r on each day is the realised toxic",
         f"share of C1 (R1), B3 (R_B3) or B2b (R_B2b) in run {canaries.name}. Three seeds each; the bare",
         "label (R1) is the mean over the seeds of each day's value. B1, C1, B3 and B2b run again in",
         f"this run so each comparison is within one run; against run {canaries.name}: {reproduced(mr, mc)}.", "",
         "| Strategy | Fills a day | Mean daily BEF bp | Markout 1 s bp | Toxic share | Toxic episodes an hour |",
         "|---|---|---|---|---|---|"]  # fmt: skip
    order = ["B1", "C1", "R1", "R1_s1", "R1_s2", "R1_s3", "B3", "R_B3", "R_B3_s1", "R_B3_s2",
             "R_B3_s3", "B2b", "R_B2b", "R_B2b_s1", "R_B2b_s2", "R_B2b_s3"]  # fmt: skip
    for lab in order:
        g = m.filter(pl.col("label") == lab)
        L.append(f"| {lab} | {g['fills'].mean():.0f} | {fmt(g[BEF].mean())} | {fmt(g['mean_markout_1s_bps'].mean())} | "
                 f"{fmt(g['toxic_share'].mean(), 4)} | {g['toxic_episodes'].mean() / hours:.0f} |")  # fmt: skip
    verdict = {True: "passes", False: "fails", None: "no verdict"}[c1["pass"]]
    L += ["", "### C1 against R1 (the section 10 pass rule since 2026-10-26)", "", *CMP_HEAD,
          cmp_row("C1 - R1 (pass: interval includes 0)", c1),
          cmp_row("C1 - B1 (the rule first written, reported)", c1["vs_B1"]),
          cmp_row("C1 - B3 (descriptive)", c1["vs_B3"]),
          *(cmp_row(f"C1 - R1_s{k} (one seed)", analysis.compare(m, "C1", f"R1_s{k}")) for k in (1, 2, 3)),
          cmp_row("R1 - B1 (the cost of random pulls at C1's rate)", analysis.compare(m, "R1", "B1")),
          "", f"- AC4.3 as revised, the C1 interval against R1 includes 0: {verdict}.",
          f"- Statement from eval/analysis.canaries on this run: {can['statement']}",
          "", "### Exploratory: the selected overlays against random pulls at their own rates", "",
          "Exploratory, not a test of section 7 or 10. Reported in the paper as exploratory.", "",
          *CMP_HEAD,
          cmp_row("B3 - R_B3", analysis.compare(m, "B3", "R_B3")),
          cmp_row("B2b - R_B2b", analysis.compare(m, "B2b", "R_B2b")),
          cmp_row("R_B3 - B1", analysis.compare(m, "R_B3", "B1")),
          cmp_row("R_B2b - B1", analysis.compare(m, "R_B2b", "B1")),
          "", "### Exploratory: B3 against B2b at matched p", "",
          "Runs " + ", ".join(x["config_hash"] for x in metas_t) + ". Exploratory; the selected B3 is p 0.05",
          "and the selected B2b p 0.25, so H1's pair compares different pull rates.", "",
          *matched_p(mt, selected)]  # fmt: skip
    out = ROOT / "docs" / "M4_v2_draft.md"
    text = out.read_text()
    keep = text.split("\n" + RANDOM_HEAD)[0].rstrip("\n")
    out.write_text(keep + "\n\n" + "\n".join(L) + "\n")
    print(out, "C1 vs R1:", verdict, fmt(c1["mean"]), ci(c1["bootstrap_ci"]))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--tune", type=Path, nargs=2, required=True)
    r = sub.add_parser("report")
    r.add_argument("--train-b", type=Path, required=True)
    r.add_argument("--tune", type=Path, nargs=2, required=True)
    r.add_argument("--canaries", type=Path, required=True)
    r.add_argument("--mde", type=Path, required=True)
    q = sub.add_parser("random")
    q.add_argument("--random", type=Path, required=True)
    q.add_argument("--canaries", type=Path, required=True)
    q.add_argument("--tune", type=Path, nargs=2, required=True)
    a = p.parse_args()
    if a.cmd == "select":
        cmd_select(a.tune)
    elif a.cmd == "random":
        cmd_random(a.random, a.canaries, a.tune)
    else:
        cmd_report(a.train_b, a.tune, a.canaries, a.mde)


if __name__ == "__main__":
    main()
