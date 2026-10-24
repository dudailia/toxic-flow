# Proposed checks for M2 (scripts/check_milestone.py)

scripts/check_milestone.py is protected, so this is a proposal for Ilia to approve and
paste in: add `import polars as pl` next to `import yaml`, paste the code above
`MILESTONES`, and add `"M2": m2` to it. Each check maps to one acceptance criterion in
SPEC.md M2.

| AC | Check | State now |
|---|---|---|
| AC2.1 | metrics rows for B0 and B1 on all 12 train days in all 8 cells, from runs not labelled smoke | only the smoke run exists |
| AC2.2 | in every results/*/metrics.parquet, smoke included, gross PnL from fills equals engine cash plus inventory times the mark mid to 1e-6 USDT | passes on the 16 smoke rows |
| AC2.3 | runs the slow fee-equivalence test (about 35 s) | passes |
| AC2.4 | for B1 on every train day and latency, the risk-averse model has no more fills than any other queue model | needs the 12 train days; the smoke day shows it |
| AC2.5 | configs/selected.yaml names B0 h and B1 gamma and window_s, and they maximise the mean daily break-even fee over train days in the primary cell (risk-averse, high latency) among the runs present | not written; it needs all 12 train days |
| AC2.6 | tests/leakage/test_layering.py has the layering test | written in tests/pending_leakage/; Ilia moves it |

Choices to confirm:
- AC2.4 counts a tie as passing ("no more fills than"). Decided by Ilia on 2026-10-24
  (Q42); SPEC.md now says the same.
- AC2.2 reads every run, smoke included, because the accounting must hold everywhere.
- AC2.5 recomputes the selection from the results rather than trusting the table in
  configs/selected.yaml, so a hand-edited table cannot pass it.
- m2_runs stores the run's label as run_label. Changed on 2026-10-23: metrics now have a
  label column of their own (the strategy label, such as C4_x10), which the earlier
  version would have overwritten.

## Proposed code

```python
M2_QUEUES = ("risk_averse", "power3", "power2", "log")
M2_LATENCIES = ("low", "high")


def m2_runs(include_smoke: bool) -> "pl.DataFrame | None":
    frames = []
    for p in sorted((ROOT / "results").glob("*/metrics.parquet")):
        meta = json.loads((p.parent / "meta.json").read_text())
        if include_smoke or meta.get("label") != "smoke":
            frames.append(
                pl.read_parquet(p).with_columns(pl.lit(meta.get("label", "")).alias("run_label"))
            )
    return pl.concat(frames, how="diagonal") if frames else None


def m2(r: Results) -> None:
    splits = check_splits(r)
    train = splits["train"]
    runs = m2_runs(include_smoke=False)
    have = set()
    if runs is not None:
        have = set(runs.select(["strategy", "day", "queue", "latency"]).iter_rows())
    missing = [
        (s, d, q, lat)
        for s in ("B0", "B1")
        for d in train
        for q in M2_QUEUES
        for lat in M2_LATENCIES
        if (s, d, q, lat) not in have
    ]
    r.add(
        "AC2.1 B0 and B1 on 12 train days in all 8 cells",
        not missing,
        f"missing {len(missing)} of 192",
    )

    every = m2_runs(include_smoke=True)
    if every is None:
        r.add("AC2.2 PnL reconciles to 1e-6 USDT", False, "no results")
    else:
        gap = (
            every["gross_pnl"]
            - (every["engine_cash"] + every["engine_position"] * every["mark_mid"])
        ).abs()
        r.add(
            "AC2.2 PnL reconciles to 1e-6 USDT",
            bool((gap <= 1e-6).all()),
            f"max gap {gap.max():.2e} over {len(gap)} rows",
        )

    proc = subprocess.run(
        ["uv", "run", "pytest", "tests/unit/test_accounting.py", "-m", "slow", "-q", "-k", "ac2_3"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    last = (proc.stdout + proc.stderr).strip().splitlines()
    r.add("AC2.3 fee equivalence (slow) passes", proc.returncode == 0, last[-1] if last else "")

    bad = []
    if runs is not None:
        b1 = runs.filter((pl.col("strategy") == "B1") & pl.col("day").is_in(train))
        for (day, lat), g in b1.group_by(["day", "latency"]):
            fills = dict(zip(g["queue"], g["fills"], strict=True))
            ra = fills.get("risk_averse")
            if ra is None or any(ra > fills[q] for q in M2_QUEUES[1:] if q in fills):
                bad.append((day, lat))
    r.add(
        "AC2.4 risk-averse has no more B1 fills than any other queue model every train day",
        runs is not None and not missing and not bad,
        f"bad {sorted(bad)[:4]}",
    )

    sel_text = read("configs/selected.yaml")
    sel = yaml.safe_load(sel_text) or {} if sel_text else {}
    chosen = (
        bool(sel)
        and all(k in sel.get("B0", {}) for k in ("h",))
        and all(k in sel.get("B1", {}) for k in ("gamma", "window_s"))
    )
    r.add("AC2.5 configs/selected.yaml has B0 h, B1 gamma and window", chosen)
    if chosen and runs is not None:
        prim = runs.filter(
            (pl.col("queue") == "risk_averse")
            & (pl.col("latency") == "high")
            & pl.col("day").is_in(train)
        )
        best = (
            prim.group_by(["strategy", "params"])
            .agg(pl.col("break_even_fee_bps").mean().alias("bef"))
            .sort("bef", descending=True)
        )
        ok = True
        for s in ("B0", "B1"):
            top = best.filter(pl.col("strategy") == s)
            if top.height:
                params = json.loads(top["params"][0])
                ok &= all(params.get(k) == v for k, v in sel[s].items() if k != "table")
        r.add("AC2.5 selection maximises the mean train BEF in the primary cell", ok)
    else:
        r.add(
            "AC2.5 selection maximises the mean train BEF in the primary cell",
            False,
            "no selection or runs",
        )

    r.add(
        "AC2.6 layering test in tests/leakage",
        "def test_ac2_6_" in read("tests/leakage/test_layering.py"),
    )
```

## Dry run on the current repo (2026-10-22, read-only)

```text
PASS  splits.venue                                                      binance-futures BTCUSDT
PASS  splits.sizes                                                      {'train': 12, 'val': 6, 'test': 16}
PASS  splits.first_of_month                                             
PASS  splits.sorted_disjoint                                            train < val < test
FAIL  AC2.1 B0 and B1 on 12 train days in all 8 cells                   missing 192 of 192
PASS  AC2.2 PnL reconciles to 1e-6 USDT                                 max gap 7.11e-12 over 16 rows
PASS  AC2.3 fee equivalence (slow) passes                               1 passed, 2 deselected in 32.36s
FAIL  AC2.4 risk-averse has the fewest B1 fills every train day         bad []
FAIL  AC2.5 configs/selected.yaml has B0 h, B1 gamma and window         
FAIL  AC2.5 selection maximises the mean train BEF in the primary cell  no selection or runs
FAIL  AC2.6 layering test in tests/leakage                              

6/11 passed
```
