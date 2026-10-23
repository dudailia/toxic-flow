# Proposed checks for M4 and M5 (scripts/check_milestone.py)

scripts/check_milestone.py is protected, so this is a proposal for Ilia to approve and
paste in: add `import polars as pl` next to `import yaml` (the M2 proposal adds it too),
paste the code below above `MILESTONES`, and add `"M4": m4, "M5": m5` to it. Each check
maps to one acceptance criterion in SPEC.md. The runs it reads are the configs written by
scripts/make_configs.py: tune_val, canaries_val and mde_train for M4, confirmatory for M5.

| AC | Check | State now |
|---|---|---|
| AC4.1 | configs/selected.yaml has B2, B2b and B3; docs/selection/<name>_val.md exists for each; the section 4 rule recomputed on the tune_val run over the non-excluded validation days picks the same settings | nothing selected yet |
| AC4.2 | on canaries_val, C2 minus B1 in the primary cell exceeds 3 times the MDE, with s from mde_train (training days) and canaries_val (validation days) and n = 16 | runs not made |
| AC4.3 | on canaries_val, the bootstrap interval of C1 minus B1 includes 0 | runs not made |
| AC4.4 | no "[TBD" in PREREGISTRATION.md and tests/test_writing.py passes | 12 [TBD] left |
| AC4.5 | not checked: the viva is Ilia's to record | |
| AC5.1 | every test-day entry in data/manifest.json has downloaded_at after the creation time of tag prereg-v1, and there is at least one | no tag |
| AC5.2 | for each test day with a result, the first commit that names the day in docs/data_quality/EXCLUSIONS.md precedes the first run that includes it | no test runs |
| AC5.3 | at least one non-smoke run touches the test days, and every one after the first has its config hash in DEVIATIONS.md | no test runs |
| AC5.4 | docs/audit_M5.md exists and is not empty | missing |

Choices to confirm:
- AC4.1 recomputes the selection from the results instead of trusting selected.yaml, and
  expects the selection tables in docs/selection/, as written by
  `scripts/select_params.py results/<hash> <name> docs/selection/<name>_val.md`.
- AC4.2 and AC4.3 follow section 10 as written. If the Q28 proposal is accepted, AC4.3
  compares C1 with B3 at c = 0 instead of B1.
- AC4.5 is left out of the script, since only Ilia runs /viva.
- AC5.2 dates the exclusion step by the commit that first names the day in EXCLUSIONS.md,
  so the exclusions file must be committed before the confirmatory run starts.

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
    tune = study_runs("tune_val")
    problems = []
    for name in ("B2", "B2b", "B3"):
        table = f"docs/selection/{name}_val.md"
        if name not in selected or not (ROOT / table).exists():
            problems.append(f"{name}: entry or {table} missing")
        elif tune is None:
            problems.append(f"{name}: no tune_val run")
        else:
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
        "AC4.3 C1 interval against B1 includes 0",
    )
    can, mde_tr = study_runs("canaries_val"), study_runs("mde_train")
    if can is None or mde_tr is None:
        r.add(c2_id, False, "needs the canaries_val and mde_train runs")
        r.add(c1_id, False, "needs the canaries_val run")
    else:
        can = can.filter(pl.col("day").is_in(val))
        mde_in = analysis.mde_inputs(
            mde_tr.filter(pl.col("day").is_in(train)), can, SPLIT_SIZES["test"]
        )
        c = analysis.canaries(can, mde_in["mde_bp"])
        c2, c1 = c.get("C2", {}), c.get("C1", {})
        r.add(
            c2_id,
            bool(c2.get("pass")),
            f"gain {c2.get('mean', float('nan')):.3f} bp, 3 x MDE {3 * mde_in['mde_bp']:.3f} bp",
        )
        r.add(c1_id, bool(c1.get("pass")), f"bootstrap interval {c1.get('bootstrap_ci')}")

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


def tag_created() -> "datetime | None":
    out = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "for-each-ref",
            "refs/tags/prereg-v1",
            "--format=%(creatordate:iso-strict)",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return datetime.fromisoformat(out) if out else None


def test_runs(test: list[str]) -> list[tuple[dict, list[str]]]:
    """(meta, test days) for every non-smoke results directory that touches a test day."""
    out = []
    for p in sorted((ROOT / "results").glob("*/meta.json")):
        meta = json.loads(p.read_text())
        days = [str(d) for d in yaml.safe_load((p.parent / "config.yaml").read_text())["days"]]
        if meta.get("label") != "smoke" and set(days) & set(test):
            out.append((meta, sorted(set(days) & set(test))))
    return out


def m5(r: Results) -> None:
    test = check_splits(r)["test"]
    created = tag_created()
    manifest = json.loads(read("data/manifest.json") or '{"files": []}')["files"]
    entries = [e for e in manifest if e["date"] in test]
    early = [
        e["path"]
        for e in entries
        if created is None or datetime.fromisoformat(e["downloaded_at"]) <= created
    ]
    r.add(
        "AC5.1 every test-day download is later than the tag",
        bool(entries) and not early,
        f"{len(entries)} test entries, {len(early)} not after the tag"
        if created
        else "no prereg-v1 tag",
    )

    runs = test_runs(test)
    starts: dict[str, datetime] = {}
    for meta, days in runs:
        t = datetime.fromisoformat(meta["started_at"])
        for d in days:
            starts[d] = min(starts.get(d, t), t)
    late = []
    for d, t in starts.items():
        # The first commit that names the day in EXCLUSIONS.md must precede its first run.
        log = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "log",
                "--reverse",
                "--format=%cI",
                "-S",
                d,
                "--",
                "docs/data_quality/EXCLUSIONS.md",
            ],
            capture_output=True,
            text=True,
        ).stdout.split()
        if not log or datetime.fromisoformat(log[0]) >= t:
            late.append(d)
    r.add(
        "AC5.2 exclusion rules applied before any result on a test day",
        bool(starts) and not late,
        f"{len(starts)} test days with results, {len(late)} without an earlier exclusion record",
    )

    deviations = read("DEVIATIONS.md")
    ordered = sorted(runs, key=lambda x: x[0]["started_at"])
    unlisted = [m["config_hash"] for m, _ in ordered[1:] if m["config_hash"] not in deviations]
    r.add(
        "AC5.3 one confirmatory results directory; any rerun named in DEVIATIONS.md",
        bool(runs) and not unlisted,
        f"{len(runs)} test-day runs, {len(unlisted)} reruns not in DEVIATIONS.md",
    )
    audit = read("docs/audit_M5.md")
    r.add(
        "AC5.4 leakage-auditor report in docs/audit_M5.md",
        bool(audit.strip()),
        f"{len(audit)} characters",
    )
```

## Dry run on the repo as it is

The code above was run inside check_milestone.py's namespace (its Results, ROOT,
check_splits and read), writing nothing:

```text
== m4
FAIL  AC4.1 selected.yaml has B2, B2b and B3 by the section 4 rule       B2: entry or docs/selection/B2_val.md missing; B2b: entry or docs/selection/B2b_val.md missing; B3: entry or docs/selection/B3_val.md missing
FAIL  AC4.2 C2 beats B1 by more than 3 x MDE                             needs the canaries_val and mde_train runs
FAIL  AC4.3 C1 interval against B1 includes 0                            needs the canaries_val run
FAIL  AC4.4 PREREGISTRATION.md has no [TBD] and passes the writing lint  12 [TBD] left; writing lint exit 0

4/8 passed
== m5
FAIL  AC5.1 every test-day download is later than the tag                         no prereg-v1 tag
FAIL  AC5.2 exclusion rules applied before any result on a test day               0 test days with results, 0 without an earlier exclusion record
FAIL  AC5.3 one confirmatory results directory; any rerun named in DEVIATIONS.md  0 test-day runs, 0 reruns not in DEVIATIONS.md
FAIL  AC5.4 leakage-auditor report in docs/audit_M5.md                            0 characters

4/8 passed
```

## Positive control

The same code against a temporary root with synthetic results: a tune_val run in which
each strategy's selected settings beat c = d = 0, a canaries_val run in which C2 beats B1
by 2 bp and C1 tracks B1, an mde_train run, a selected.yaml and the three tables:

```text
PASS  AC4.1 selected.yaml has B2, B2b and B3 by the section 4 rule       matches the rule on the validation days
PASS  AC4.2 C2 beats B1 by more than 3 x MDE                             gain 2.000 bp, 3 x MDE 0.155 bp
PASS  AC4.3 C1 interval against B1 includes 0                            bootstrap interval (-0.04145862950838373, 0.027110772635426734)
FAIL  AC4.4 PREREGISTRATION.md has no [TBD] and passes the writing lint  0 [TBD] left; writing lint exit 4

7/8 passed
```

AC4.4 fails there only because the temporary root has no tests directory and no
PREREGISTRATION.md, so the lint cannot run; on the repo it reports the [TBD] count.
