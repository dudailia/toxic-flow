# Proposed checks for M4 under v2 (scripts/check_milestone.py)

This replaces the M4 part of docs/proposals/check_M4_M5.md, which reads the v1 configs (tune_val, canaries_val,
mde_train) and judges C1 against B1. The M5 part of that file is unchanged. Under v2 the
M4 runs are the configs written by scripts/make_v2_configs.py: v2_tune_val_a and
v2_tune_val_b (tuning, two halves of the validation days), v2_canaries_val (C2 and the
validation estimate of s), v2_mde_train (the training estimate of s) and
v2_random_pulls_val (C1 against R1, section 10 as revised on 2026-10-26).

scripts/check_milestone.py is protected, so this is a proposal for Ilia to approve and
paste in: add `import polars as pl` next to `import yaml`, paste the code below above
`MILESTONES`, and add `"M4": m4` to it. If the M4_M5 proposal's `study_runs` and `kept`
are pasted too, keep one copy of each.

| AC | Check |
|---|---|
| AC4.1 | configs/selected.yaml has B2, B2b and B3, and the section 4 rule recomputed on the two tuning runs over the non-excluded validation days picks the same settings |
| AC4.2 | on v2_canaries_val, C2 minus B1 in the primary cell exceeds 3 times the MDE, with s from v2_mde_train and v2_canaries_val and n = 16 |
| AC4.3 | on v2_random_pulls_val, the analysis judges C1 against R1 (the mean of R1_s1 to R1_s3 per day) and the bootstrap interval includes 0 |
| AC4.4 | no "[TBD" in PREREGISTRATION.md and tests/test_writing.py passes |
| AC4.5 | not checked: the viva is Ilia's to record |

Dry run: the code below, executed in the namespace of the current scripts/check_milestone.py
without changing it, gives the state recorded in docs/TAG_CHECKLIST.md.

## Proposed code

```python
def study_runs(config: str) -> "pl.DataFrame | None":
    """Metrics of the non-smoke runs of configs/runs/<config>.yaml."""
    frames = []
    for p in sorted((ROOT / "results").glob("*/metrics.parquet")):
        meta = json.loads((p.parent / "meta.json").read_text())
        if meta.get("config") == f"configs/runs/{config}.yaml" and meta.get("label") != "smoke":
            frames.append(pl.read_parquet(p))
    return pl.concat(frames, how="diagonal_relaxed") if frames else None


def kept(days: list[str]) -> list[str]:
    from toxic_flow.data.exclusions import excluded_days

    return [d for d in days if d not in excluded_days(days)]


def m4(r: Results) -> None:
    from toxic_flow.eval import analysis
    from toxic_flow.eval.select import candidate_table, select

    splits = check_splits(r)
    val, train = kept(splits["val"]), kept(splits["train"])
    sel_file = ROOT / "configs" / "selected.yaml"
    selected = yaml.safe_load(sel_file.read_text()) if sel_file.exists() else {}
    halves = [study_runs(c) for c in ("v2_tune_val_a", "v2_tune_val_b")]
    problems = []
    if any(h is None for h in halves):
        problems.append("needs the v2_tune_val_a and v2_tune_val_b runs")
    else:
        tune = pl.concat(halves, how="diagonal_relaxed")
        for name in ("B2", "B2b", "B3"):
            if name not in selected:
                problems.append(f"{name}: no entry")
                continue
            try:
                pick = select(candidate_table(tune, name, val), name)["params"]
            except ValueError as e:
                problems.append(f"{name}: {e}")
                continue
            if any(pick.get(k) != v for k, v in selected[name].items()):
                problems.append(f"{name}: differs from the rule's choice {pick}")
    r.add(
        "AC4.1 selected.yaml has B2, B2b and B3 by the section 4 rule",
        not problems,
        "; ".join(problems) or "matches the rule on the validation days",
    )

    c2_id, c1_id = (
        "AC4.2 C2 beats B1 by more than 3 x MDE",
        "AC4.3 C1 interval against R1 includes 0",
    )
    can, mde_tr = study_runs("v2_canaries_val"), study_runs("v2_mde_train")
    if can is None or mde_tr is None:
        r.add(c2_id, False, "needs the v2_canaries_val and v2_mde_train runs")
    else:
        can = can.filter(pl.col("day").is_in(val))
        mde_in = analysis.mde_inputs(
            mde_tr.filter(pl.col("day").is_in(train)), can, SPLIT_SIZES["test"]
        )
        c2 = analysis.canaries(can, mde_in["mde_bp"]).get("C2", {})
        r.add(
            c2_id,
            bool(c2.get("pass")),
            f"gain {c2.get('mean', float('nan')):.3f} bp, 3 x MDE {3 * mde_in['mde_bp']:.3f} bp",
        )
    rnd = study_runs("v2_random_pulls_val")
    if rnd is None:
        r.add(c1_id, False, "needs the v2_random_pulls_val run")
    else:
        c1 = analysis.canaries(rnd.filter(pl.col("day").is_in(val)), float("nan")).get("C1", {})
        r.add(
            c1_id,
            c1.get("rule") == "C1 - R1" and bool(c1.get("pass")),
            f"{c1.get('rule')}: bootstrap interval {c1.get('bootstrap_ci')}",
        )

    tbd = read("PREREGISTRATION.md").count("[TBD")
    lint = subprocess.run(
        ["uv", "run", "pytest", "tests/test_writing.py", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    r.add(
        "AC4.4 PREREGISTRATION.md has no [TBD] and passes the writing lint",
        tbd == 0 and lint.returncode == 0,
        f"{tbd} [TBD] left; writing lint exit {lint.returncode}",
    )
```
