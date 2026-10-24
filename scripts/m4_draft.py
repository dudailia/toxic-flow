#!/usr/bin/env python3
"""M4 draft from results/ only: the overlay choice on validation days, the canaries and
the MDE, for Ilia's review before anything goes into PREREGISTRATION.md or
configs/selected.yaml (Ilia, 2026-10-24).

  uv run python scripts/m4_draft.py select results/<tune_val>
      Section 4 overlay rule on the validation days, primary cell. Writes
      docs/M4_draft_selected.yaml: B0 and B1 from configs/selected.yaml plus the draft B2,
      B2b and B3 choices, which make_configs.py --selected reads for the canary and
      training runs.
  uv run python scripts/m4_draft.py report --tune results/<h> --canaries results/<h> --train results/<h>
      Writes docs/M4_draft.md: the tuning tables, the canaries by section 10 and the MDE
      by section 9 (s from the training run and from the canary run's B2b and B3).
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
from toxic_flow.eval.select import PRIMARY, candidate_table, select

ROOT = Path(__file__).resolve().parents[1]
DRAFT_SELECTED = ROOT / "docs" / "M4_draft_selected.yaml"
OVERLAYS = ("B2", "B2b", "B3")


def kept(split: str) -> list[str]:
    days = load_splits()[split]
    return sorted(d for d in days if d not in excluded_days(days))


def load(run_dir: Path, config: str, split: str) -> tuple[pl.DataFrame, dict]:
    """A run's metrics, refused unless it is the named config on every kept day."""
    meta = json.loads((run_dir / "meta.json").read_text())
    m = pl.read_parquet(run_dir / "metrics.parquet")
    if meta["config"] != f"configs/runs/{config}.yaml" or sorted(set(m["day"])) != kept(split):
        raise SystemExit(f"{run_dir} is not {config} on the kept {split} days")
    return m, meta


def fmt(x: float) -> str:
    return "none" if x is None or not np.isfinite(x) else f"{x:.4f}"


def ci(c: tuple) -> str:
    return f"[{fmt(c[0])}, {fmt(c[1])}]"


def cmp_row(name: str, c: dict) -> str:
    return (f"| {name} | {c['n']} | {fmt(c['mean'])} | {ci(c['bootstrap_ci'])} | {ci(c['t_ci'])} "
            f"| {c['n_positive']} | {', '.join(c['dropped']) or 'none'} |")  # fmt: skip


CMP_HEAD = [
    "| Comparison | Days | Mean bp | Bootstrap 95% | t 95% | Days > 0 | Dropped (no fills) |",
    "|---|---|---|---|---|---|---|",
]


def cmd_select(tune: Path) -> None:
    m, meta = load(tune, "tune_val", "val")
    approved = yaml.safe_load((ROOT / "configs" / "selected.yaml").read_text())
    out = {"draft": f"M4 draft from run {meta['config_hash']}, not approved",
           "B0": approved["B0"], "B1": approved["B1"]}  # fmt: skip
    for name in OVERLAYS:
        pick = select(candidate_table(m, name, kept("val")), name)
        out[name] = {
            k: v for k, v in pick["params"].items() if k in ("c", "d", "ofi_window_s", "tau_s")
        }
    DRAFT_SELECTED.write_text(
        "# Draft overlay choice for Ilia's review (scripts/m4_draft.py select). Not\n"
        "# configs/selected.yaml: make_configs.py --selected reads it for the draft runs.\n"
        + yaml.safe_dump(out, sort_keys=False)
    )
    print(DRAFT_SELECTED, json.dumps({k: out[k] for k in OVERLAYS}))


def tuning_section(m: pl.DataFrame, meta: dict) -> list[str]:
    days = kept("val")
    lines = [
        "## Overlay tuning on the validation days (section 4)",
        "",
        f"Run {meta['config_hash']} ({meta['config']}, commit {meta['commit'][:7]}), primary cell "
        f"{PRIMARY[0]} / {PRIMARY[1]}, {len(days)} days: {', '.join(days)}. Rule: highest mean "
        "daily break-even fee; ties to the smaller c + d, then the shorter window or decay.",
    ]
    for name in OVERLAYS:
        table = candidate_table(m, name, days).with_columns(pl.col("mean_bef_bps").fill_nan(None))
        pick = select(table, name)
        lines += ["", f"### {name}", "",
                  "| Candidate | Mean daily BEF bp | Days without fills | Median daily fills |",
                  "|---|---|---|---|"]  # fmt: skip
        for r in table.sort("mean_bef_bps", descending=True, nulls_last=True).iter_rows(named=True):
            p = {
                k: v
                for k, v in json.loads(r["params"]).items()
                if k in ("c", "d", "ofi_window_s", "tau_s")
            }
            lines.append(f"| {json.dumps(p)} | {fmt(r['mean_bef_bps'])} | {r['zero_fill_days']} "
                         f"| {r['median_fills']:.0f} |")  # fmt: skip
        chosen = {
            k: v for k, v in pick["params"].items() if k in ("c", "d", "ofi_window_s", "tau_s")
        }
        lines += ["", f"Draft choice: {json.dumps(chosen)}, mean daily BEF {fmt(pick['mean_bef_bps'])} bp"
                  + (f", {pick['tied']} candidates tied at the top." if pick["tied"] > 1 else ".")]  # fmt: skip
    return lines


def cmd_report(tune: Path, canaries: Path, train: Path) -> None:
    mt, meta_t = load(tune, "tune_val", "val")
    mc, meta_c = load(canaries, "canaries_val_draft", "val")
    mtr, meta_tr = load(train, "mde_train_draft", "train")
    n_test = len(load_splits()["test"])  # the count only; no test-day data is read
    mde = analysis.mde_inputs(mtr, mc, n_test)
    can = analysis.canaries(mc, mde["mde_bp"])
    lines = [
        "# M4 draft: overlay tuning, canaries and MDE (for Ilia's review)",
        "",
        "Draft only. Nothing here is in PREREGISTRATION.md or configs/selected.yaml; every [TBD]",
        "there is unchanged. All numbers come from the three runs named below, through",
        "scripts/m4_draft.py. Validation and training days only; no test day was loaded.",
        "",
        *tuning_section(mt, meta_t),
        "",
        "## Minimum detectable effect (section 9)",
        "",
        "s is the larger of the standard deviations of D_i = BEF_B3 - BEF_B2b with the draft",
        f"settings: on the training days (run {meta_tr['config_hash']}) and on the validation days",
        f"(run {meta_c['config_hash']}). n = {n_test} test days.",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| s on training days, bp | {fmt(mde['s_train_bp'])} |",
        f"| s on validation days, bp | {fmt(mde['s_val_bp'])} |",
        f"| s, bp | {fmt(mde['s_bp'])} |",
        f"| MDE = 0.70 s, bp | {fmt(mde['mde_bp'])} |",
        f"| 3 x MDE (C2 threshold), bp | {fmt(3 * mde['mde_bp'])} |",
        "",
        "## Canaries on the validation days (section 10)",
        "",
        f"Run {meta_c['config_hash']} ({meta_c['config']}, commit {meta_c['commit'][:7]}), primary cell;",
        "C3 is B3 at zero latency in the risk-averse queue model.",
        "",
        *CMP_HEAD,
    ]
    rows = []
    if "C1" in can:
        rows.append(("C1 - B1 (pass: interval includes 0)", can["C1"]))
        if "vs_B3" in can["C1"]:
            rows.append(("C1 - B3 (descriptive)", can["C1"]["vs_B3"]))
    if "C2" in can:
        rows.append(("C2 - B1 (pass: mean above 3 x MDE)", can["C2"]))
    for v in sorted(k for k in can.get("C4", {}) if k.startswith("C4")):
        rows.append((f"{v} - B3", can["C4"][v]))
    labels = set(analysis._labelled(mc)["label"])
    if {"B3_c0", "C1_c0"} <= labels:
        # Leakage audit A1 (Q44): the same pair with c = 0, so C1's random u cannot move
        # the quote centre. Descriptive.
        rows += [("B3 with c = 0 - B1 (descriptive)", analysis.compare(mc, "B3_c0", "B1")),
                 ("C1 with c = 0 - B1 (descriptive)", analysis.compare(mc, "C1_c0", "B1")),
                 ("C1 with c = 0 - B3 with c = 0 (descriptive)", analysis.compare(mc, "C1_c0", "B3_c0"))]  # fmt: skip
    lines += [cmp_row(n, c) for n, c in rows]
    verdict = {True: "passes", False: "fails", None: "no verdict"}
    c3 = can.get("C3", {})
    lines += [
        "",
        f"- AC4.2, C2 beats B1 by more than 3 x MDE: {verdict[can['C2']['pass']] if 'C2' in can else 'not run'}.",
        f"- AC4.3, the C1 interval against B1 includes 0: {verdict[can['C1']['pass']] if 'C1' in can else 'not run'}.",
        "- C3, mean BEF of B3 by latency, bp: "
        + ", ".join(f"{k} {fmt(v)}" for k, v in c3.get("mean_bef_bp", {}).items())
        + f"; flag (a non-zero latency above zero latency): {c3.get('flag')}.",
        f"- C4, matches B3 within the interval: {can.get('C4', {}).get('matches_b3')}.",
        "",
        f"Statement from eval/analysis.canaries: {can['statement']}",
    ]
    out = ROOT / "docs" / "M4_draft.md"
    out.write_text("\n".join(lines) + "\n")
    print(out)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select").add_argument("tune", type=Path)
    r = sub.add_parser("report")
    for k in ("tune", "canaries", "train"):
        r.add_argument(f"--{k}", type=Path, required=True)
    a = p.parse_args()
    if a.cmd == "select":
        cmd_select(a.tune)
    else:
        cmd_report(a.tune, a.canaries, a.train)


if __name__ == "__main__":
    main()
