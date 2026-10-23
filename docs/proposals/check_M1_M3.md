# Proposed checks for M1 and M3 (scripts/check_milestone.py)

scripts/check_milestone.py is protected, so these are proposals for Ilia to approve and
paste in. Each check maps to one acceptance criterion in SPEC.md. To apply: add
`import polars as pl` next to `import yaml`, paste the two functions above `MILESTONES`,
and set `MILESTONES = {"M0": m0, "M1": m1, "M3": m3}`.

## What each check needs

| AC | Check | Built now? |
|---|---|---|
| AC1.1 | 36 train and val files in data/manifest.json, no test date | 1 of 18 days downloaded (Tardis rate limit, no requests until Ilia says so) |
| AC1.2 | tests/unit/test_raw_hashes.py exists, marked slow, re-hashes against the manifest | not yet written |
| AC1.3 | docs/data_quality/DATE.json for all 18 days; every day with an exclusion rule true is in docs/data_quality/EXCLUSIONS.md with "rule N", and no other day is | validate.py writes the file; 1 of 18 days |
| AC1.4 | the two collapse unit tests exist (make check runs them) | yes |
| AC1.5 | data/events/DATE.parquet for all 18 days, exact schema | 1 of 18 days |
| AC1.6 | bytes recorded for all 36 files in the manifest | 2 of 36 |
| AC3.1 | perturbation tests for EWMA, Hawkes and OFI in tests/leakage/ | written in tests/pending_leakage/; Ilia moves them |
| AC3.2 | online-equals-offline test exists with rtol 1e-9 | yes |
| AC3.3 | the slow recovery test passes (runs it, about 5 s) | yes |
| AC3.4 | docs/hawkes_fit.json from the 12 training days has branching_ratio below 1 | needs the training days |
| AC3.5 | docs/hawkes_fit.md has "## Time-rescaling residuals" and KS statistics | needs the validation days |
| AC3.6 | tests/canary/ holds the C2 oracle test; no file in strategies/ or signals/ names a forward array (`future_mid`, `forward_*`) | canary not yet written; the name rule is a proposal to fix now |

Notes for Ilia:
- AC1.3 reads "rule N" from EXCLUSIONS.md, so the file should name rules as "rule 1" to
  "rule 3".
- AC3.6's forward-array names are a convention to adopt before the canary exists: the
  oracle's arrays are named `future_mid` or `forward_*`, and nothing else may use them.
- AC3.3 runs a slow test inside the check, about 5 s.

## Proposed code

```python
def m1(r: Results) -> None:
    splits = check_splits(r)
    days = splits["train"] + splits["val"]
    test_dates = set(splits["test"])
    entries = json.loads(read("data/manifest.json") or '{"files": []}')["files"]
    have = {(e.get("date"), e.get("data_type")) for e in entries}
    missing = [(d, t) for d in days for t in DATA_TYPES if (d, t) not in have]
    r.add("AC1.1 manifest has 36 train and val files", not missing, f"missing {len(missing)}")
    r.add("AC1.1 no test date in manifest", not any(e.get("date") in test_dates for e in entries))

    slow = read("tests/unit/test_raw_hashes.py")
    r.add("AC1.2 slow re-hash test exists", "pytest.mark.slow" in slow and "sha256" in slow)

    quality = ROOT / "docs" / "data_quality"
    reports = {d: quality / f"{d}.json" for d in days}
    r.add(
        "AC1.3 data-quality file per day",
        all(p.exists() for p in reports.values()),
        f"missing {[d for d, p in reports.items() if not p.exists()][:4]}",
    )
    flagged = {}
    for d, p in reports.items():
        if p.exists():
            q = json.loads(p.read_text())
            rules = [n for n in (1, 2, 3) if q.get(f"exclusion_rule_{n}")]
            if rules:
                flagged[d] = rules
    listed = read("docs/data_quality/EXCLUSIONS.md")
    listed_days = set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", listed))
    ok = all(
        d in listed_days and all(f"rule {n}" in listed for n in rules)
        for d, rules in flagged.items()
    )
    r.add(
        "AC1.3 excluded days listed with rule numbers",
        ok and listed_days <= set(flagged),
        f"flagged {flagged}, listed {sorted(listed_days)}",
    )

    tests = read("tests/unit/test_market_orders.py")
    r.add(
        "AC1.4 collapse unit tests exist",
        "def test_ac1_4_three_prints" in tests and "def test_ac1_4_opposite_sides" in tests,
    )

    want = ["exch_ts", "local_ts", "side", "size", "vwap", "n_prints", "levels"]
    bad = []
    for d in days:
        p = ROOT / "data" / "events" / f"{d}.parquet"
        if not p.exists() or pl.read_parquet_schema(p) != dict(
            zip(want, [pl.Int64, pl.Int64, pl.String, pl.Float64, pl.Float64, pl.Int64, pl.Int64])
        ):
            bad.append(d)
    r.add("AC1.5 event table per day with the schema", not bad, f"bad {bad[:4]}")

    sized = [
        e
        for e in entries
        if e.get("date") in days and isinstance(e.get("bytes"), int) and e["bytes"] > 0
    ]
    r.add(
        "AC1.6 bytes recorded for all 36 train and val files",
        len(sized) == 2 * len(days),
        f"{len(sized)}",
    )


def m3(r: Results) -> None:
    check_splits(r)
    leak = read("tests/leakage/test_future_perturbation.py")
    r.add(
        "AC3.1 perturbation test per signal in tests/leakage",
        all(s in leak for s in ("ewma_at", "hawkes_signal", "ofi_signal")),
    )
    hawkes = read("tests/unit/test_hawkes.py")
    r.add(
        "AC3.2 online equals offline test exists",
        "def test_ac3_2_" in hawkes and "rtol=1e-9" in hawkes,
    )
    proc = subprocess.run(
        ["uv", "run", "pytest", "tests/unit/test_hawkes.py", "-m", "slow", "-q", "-k", "ac3_3"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    last = (proc.stdout + proc.stderr).strip().splitlines()
    r.add("AC3.3 parameter recovery (slow) passes", proc.returncode == 0, last[-1] if last else "")
    fit_text = read("docs/hawkes_fit.json")
    br = json.loads(fit_text).get("branching_ratio") if fit_text else None
    r.add("AC3.4 fitted branching ratio below 1", br is not None and br < 1, f"{br}")
    doc = read("docs/hawkes_fit.md")
    r.add(
        "AC3.5 docs/hawkes_fit.md has residuals and KS",
        "## Time-rescaling residuals" in doc and "KS" in doc,
    )
    canary = ROOT / "tests" / "canary"
    forward = re.compile(r"\bfuture_mid\b|\bforward_\w+")
    leaks = [
        p.relative_to(ROOT).as_posix()
        for d in ("src/toxic_flow/strategies", "src/toxic_flow/signals")
        for p in (ROOT / d).rglob("*.py")
        if forward.search(p.read_text())
    ]
    r.add(
        "AC3.6 oracle canary lives under tests/canary",
        canary.exists() and any(canary.glob("test_*c2*.py")),
    )
    r.add("AC3.6 no strategy or signal file reads forward arrays", not leaks, str(leaks[:3]))
```

## Dry run on the current repo (2026-10-22, read-only)

The functions above, appended to a scratch copy of the check script pointed at this
checkout:

```text
=== M1
PASS  splits.venue                                         binance-futures BTCUSDT
PASS  splits.sizes                                         {'train': 12, 'val': 6, 'test': 16}
PASS  splits.first_of_month                                
PASS  splits.sorted_disjoint                               train < val < test
FAIL  AC1.1 manifest has 36 train and val files            missing 34
PASS  AC1.1 no test date in manifest                       
FAIL  AC1.2 slow re-hash test exists                       
FAIL  AC1.3 data-quality file per day                      missing ['2024-02-01', '2024-03-01', '2024-04-01', '2024-05-01']
PASS  AC1.3 excluded days listed with rule numbers         flagged {}, listed []
PASS  AC1.4 collapse unit tests exist                      
FAIL  AC1.5 event table per day with the schema            bad ['2024-02-01', '2024-03-01', '2024-04-01', '2024-05-01']
FAIL  AC1.6 bytes recorded for all 36 train and val files  2

7/12 passed
exit 1
=== M3
PASS  splits.venue                                           binance-futures BTCUSDT
PASS  splits.sizes                                           {'train': 12, 'val': 6, 'test': 16}
PASS  splits.first_of_month                                  
PASS  splits.sorted_disjoint                                 train < val < test
FAIL  AC3.1 perturbation test per signal in tests/leakage    
PASS  AC3.2 online equals offline test exists                
PASS  AC3.3 parameter recovery (slow) passes                 1 passed, 5 deselected in 4.53s
FAIL  AC3.4 fitted branching ratio below 1                   None
FAIL  AC3.5 docs/hawkes_fit.md has residuals and KS          
FAIL  AC3.6 oracle canary lives under tests/canary           
PASS  AC3.6 no strategy or signal file reads forward arrays  []

7/11 passed
exit 1
```
