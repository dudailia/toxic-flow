#!/usr/bin/env python3
"""Machine-checkable acceptance criteria for the milestones in SPEC.md.

Usage: uv run python scripts/check_milestone.py M0
Exits 0 only if every criterion for that milestone passes.

This file is on .claude/protected-paths.txt. Checks for each milestone are added at the
start of that milestone and approved by Ilia before the implementation exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_TYPES = ("incremental_book_L2", "trades")
SPLIT_SIZES = {"train": 12, "val": 6, "test": 16}


class Results:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, cid: str, ok: bool, detail: str = "") -> None:
        self.rows.append((cid, bool(ok), detail))

    def report(self) -> int:
        width = max((len(c) for c, _, _ in self.rows), default=0)
        for cid, ok, detail in self.rows:
            print(f"{'PASS' if ok else 'FAIL'}  {cid:<{width}}  {detail}")
        failed = [c for c, ok, _ in self.rows if not ok]
        print(f"\n{len(self.rows) - len(failed)}/{len(self.rows)} passed")
        return 1 if failed else 0


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text() if p.exists() else ""


def load_splits() -> tuple[dict[str, list[str]], dict]:
    cfg = yaml.safe_load(read("configs/splits.yaml")) or {}
    splits = {k: [str(d) for d in cfg.get(k, [])] for k in SPLIT_SIZES}
    return splits, cfg


def check_splits(r: Results) -> dict[str, list[str]]:
    splits, cfg = load_splits()
    venue_ok = cfg.get("venue") == "binance-futures" and cfg.get("symbol") == "BTCUSDT"
    r.add("splits.venue", venue_ok, f"{cfg.get('venue')} {cfg.get('symbol')}")
    sizes = {k: len(v) for k, v in splits.items()}
    r.add("splits.sizes", sizes == SPLIT_SIZES, str(sizes))
    ordered = splits["train"] + splits["val"] + splits["test"]
    days = [date.fromisoformat(d) for d in ordered]
    r.add("splits.first_of_month", all(d.day == 1 for d in days))
    r.add("splits.sorted_disjoint", days == sorted(set(days)), "train < val < test")
    return splits


def m0(r: Results) -> None:
    splits = check_splits(r)
    dates = splits["train"] + splits["val"] + splits["test"]
    test_dates = set(splits["test"])

    recon_text = read("data/recon.json")
    if not recon_text:
        r.add("AC0.1 data/recon.json", False, "missing")
    else:
        recon = json.loads(recon_text)
        # AC0.1 as changed on 2026-10-22 (SPEC.md): datasets.tardis.dev answers HEAD with 404
        # for every URL, so coverage comes from the Tardis exchange metadata, and test-day
        # URLs get no request at all except the HEADs recon sent before that decision.
        meta = recon.get("exchange_meta") or {}
        sym = [s for s in meta.get("datasets", {}).get("symbol", []) if s.get("id") == "BTCUSDT"]
        first = datetime.combine(date.fromisoformat(dates[0]), time(), UTC)
        end = datetime.combine(date.fromisoformat(dates[-1]) + timedelta(days=1), time(), UTC)

        def utc(ts: str) -> datetime:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))

        covered = (
            len(sym) == 1
            and all(t in sym[0].get("dataTypes", []) for t in DATA_TYPES)
            and utc(sym[0]["availableSince"]) <= first
            and utc(sym[0]["availableTo"]) >= end
        )
        span = f"{sym[0]['availableSince']} to {sym[0]['availableTo']}" if sym else "no BTCUSDT"
        r.add("AC0.1 Tardis metadata covers all 34 dates", covered, span)

        # The HEADs recon sent to test-day URLs before the decision are pinned: exactly these
        # 32 rows (HEAD, 404, no size), so deleting or editing one fails the check as well.
        # Every request sent since goes through TardisClient and is logged before it is sent.
        decision = datetime(2026, 10, 22, 20, 0, tzinfo=UTC)
        frags = {d: "/" + d.replace("-", "/") + "/" for d in test_dates}

        def test_days_in(text: str) -> list[str]:
            return [d for d, frag in frags.items() if frag in text]

        contacts = sorted(
            (
                f
                for f in recon.get("files", [])
                if f.get("date") in test_dates or test_days_in(str(f.get("url", "")))
            ),
            key=lambda f: (str(f.get("date")), str(f.get("data_type"))),
        )
        pin = hashlib.sha256(json.dumps(contacts, sort_keys=True).encode()).hexdigest()
        bad = [
            (f.get("date"), f.get("data_type"))
            for f in contacts
            if f.get("method") != "HEAD"
            or f.get("status") != 404
            or "get_headers" in f
            or f.get("content_length") is not None
            or utc(f.get("checked_at") or "9999-12-31T00:00:00Z") >= decision
        ]
        rest = test_days_in(json.dumps({k: v for k, v in recon.items() if k != "files"}))
        log = ROOT / "data" / "tardis_requests.jsonl"
        logged = test_days_in(log.read_text()) if log.exists() else ["log missing"]
        # stdout of the recon run whose recon.json was discarded: "date type status size".
        old = [
            ln
            for p in sorted((ROOT / "data" / "recon_logs").glob("*.log"))
            for ln in p.read_text().splitlines()
            if ln.split(" ")[0] in test_dates
        ]
        old_bad = [ln for ln in old if not ln.endswith(" 404 None")]
        pinned = "6b150af712158efb098beb1f3a7a4cc5cc32e6c5ff16b21d18c9b8446361b7c6"
        r.add(
            "AC0.1 no test-day request beyond the recorded HEADs",
            len(contacts) == 32
            and pin == pinned
            and not bad
            and not rest
            and not logged
            and not old_bad,
            f"{len(contacts)} pinned in recon.json, {len(old)} in recon_logs; "
            f"bad {bad[:2]} {rest[:2]} {logged[:2]} {old_bad[:2]}",
        )
        meta_ok = (
            recon.get("exchange") == "binance-futures"
            and recon.get("symbol") == "BTCUSDT"
            and bool(recon.get("exchange_meta"))
        )
        r.add("AC0.2 exchange metadata recorded", meta_ok)

    venue_text = read("configs/venue.yaml")
    if not venue_text:
        r.add("AC0.3 configs/venue.yaml", False, "missing")
    else:
        venue = yaml.safe_load(venue_text) or {}
        by_date = {str(k): v or {} for k, v in (venue.get("by_date") or {}).items()}
        need = (
            "tick_size",
            "lot_size",
            "min_notional",
            "maker_fee_bps",
            "taker_fee_bps",
            "source",
        )
        gaps = [d for d in dates if any(by_date.get(d, {}).get(k) in (None, "") for k in need)]
        r.add("AC0.3 venue spec for every date", not gaps, f"gaps {gaps[:4]}")
        r.add("AC0.3 no TBD left in venue.yaml", "TBD" not in venue_text)

    sections = (
        "## Version",
        "## Data conversion",
        "## Queue models",
        "## Latency models",
        "## Exchange model",
        "## Fee model",
    )
    engine = read("docs/ENGINE.md")
    r.add("AC0.4 hftbacktest pinned in uv.lock", 'name = "hftbacktest"' in read("uv.lock"))
    r.add("AC0.4 docs/ENGINE.md sections", bool(engine) and all(s in engine for s in sections))

    r.add("AC0.5 split-lock test exists", (ROOT / "tests/leakage/test_split_lock.py").exists())
    data_dir = ROOT / "data"
    leaked = []
    if data_dir.exists():
        # os.walk follows symlinks, so data/raw moved to an external disk and linked back
        # (docs/ssd_move.md) is still searched; Path.rglob in Python 3.12 does not enter it.
        paths = [
            Path(parent) / name
            for parent, dirs, files in os.walk(data_dir, followlinks=True)
            for name in dirs + files
        ]
        leaked = [
            p.relative_to(ROOT).as_posix()
            for p in paths
            if any(t in p.as_posix() for t in test_dates)
        ]
    r.add("AC0.5 no test-day path under data/", not leaked, str(leaked[:3]))

    manifest_text = read("data/manifest.json")
    if not manifest_text:
        r.add("AC0.6 data/manifest.json", False, "missing")
    else:
        entries = json.loads(manifest_text).get("files", [])
        hashes_ok = bool(entries) and all(
            re.fullmatch(r"[0-9a-f]{64}", e.get("sha256", "")) for e in entries
        )
        r.add("AC0.6 benchmark day in manifest", any(e.get("date") == dates[0] for e in entries))
        r.add("AC0.6 manifest hashes well formed", hashes_ok)
        r.add(
            "AC0.5 no test date in manifest", not any(e.get("date") in test_dates for e in entries)
        )
    recon_md = read("docs/DATA_RECON.md")
    r.add(
        "AC0.6 DATA_RECON.md has Benchmark and Compute projection",
        "## Benchmark" in recon_md and "## Compute projection" in recon_md,
    )

    dry = subprocess.run(["make", "-n", "check"], cwd=ROOT, capture_output=True, text=True).stdout
    pytest_lines = [ln for ln in dry.splitlines() if "pytest" in ln]
    whole = any(re.search(r"\btests/?(\s|$)", ln) for ln in pytest_lines)
    leak = whole or any("tests/leakage" in ln for ln in pytest_lines)
    lint = whole or any("test_writing" in ln for ln in pytest_lines)
    r.add("AC0.7 make check runs tests/leakage", leak)
    r.add("AC0.7 make check runs the writing lint", lint)
    hook = read(".git/hooks/pre-commit")
    r.add("AC0.7 pre-commit hook runs make check", "make check" in hook)
    proc = subprocess.run(["make", "check"], cwd=ROOT, capture_output=True, text=True)
    last = (proc.stdout + proc.stderr).strip().splitlines()
    r.add("AC0.7 make check passes", proc.returncode == 0, last[-1] if last else "")


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
    # The closing "Days assessed so far" line names every assessed day; only the lines
    # above it list excluded days.
    excluded_part = listed.split("Days assessed")[0]
    listed_days = set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", excluded_part))
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
            zip(
                want,
                [pl.Int64, pl.Int64, pl.String, pl.Float64, pl.Float64, pl.Int64, pl.Int64],
                strict=True,
            )
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
    fit_text = read("docs/signals/train_constants.json")
    br = json.loads(fit_text)["hawkes"].get("branching_ratio") if fit_text else None
    r.add("AC3.4 fitted branching ratio below 1", br is not None and br < 1, f"{br}")
    doc = read("docs/hawkes_fit.md")
    r.add(
        "AC3.5 docs/hawkes_fit.md has residuals and KS",
        "## Time-rescaling diagnostics" in doc and "KS" in doc,
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


M2_QUEUES = ("risk_averse", "power3", "power2", "log")
M2_LATENCIES = ("low", "high")


def study_runs(config: str) -> pl.DataFrame | None:
    """Metrics of the non-smoke runs of configs/runs/<config>.yaml."""
    frames = []
    for p in sorted((ROOT / "results").glob("*/metrics.parquet")):
        meta = json.loads((p.parent / "meta.json").read_text())
        if meta.get("config") == f"configs/runs/{config}.yaml" and meta.get("label") != "smoke":
            frames.append(pl.read_parquet(p))
    return pl.concat(frames, how="diagonal_relaxed") if frames else None


def every_run() -> pl.DataFrame | None:
    """Metrics of every run, smoke included: the accounting must hold everywhere."""
    frames = [pl.read_parquet(p) for p in sorted((ROOT / "results").glob("*/metrics.parquet"))]
    return pl.concat(frames, how="diagonal_relaxed") if frames else None


def m2(r: Results) -> None:
    splits = check_splits(r)
    train = splits["train"]
    # AC2.1 and AC2.4 read the v2 B0 and B1 run only (SPEC.md, Ilia 2026-10-26): v1 rows
    # carry the same labels and must not stand in for it.
    runs = study_runs("v2_train")
    have = set()
    if runs is not None:
        have = set(runs.select(["strategy", "day", "queue", "latency"]).iter_rows())
    want = [
        (s, d, q, lat)
        for s in ("B0", "B1")
        for d in train
        for q in M2_QUEUES
        for lat in M2_LATENCIES
    ]
    missing = [k for k in want if k not in have]
    r.add(
        "AC2.1 v2 B0 and B1 on 12 train days in all 8 cells",
        not missing,
        f"missing {len(missing)} of {len(want)}",
    )

    every = every_run()
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
    # The test skips when 2024-01-01 is not converted; a skip proves nothing (2026-10-26).
    ran = proc.returncode == 0 and "1 passed" in (last[-1] if last else "")
    r.add("AC2.3 fee equivalence (slow) passes", ran, last[-1] if last else "")

    bad = []
    if runs is not None:
        base = runs.filter(pl.col("strategy").is_in(["B0", "B1"]) & pl.col("day").is_in(train))
        for (s, day, lat), g in base.group_by(["strategy", "day", "latency"]):
            fills = dict(zip(g["queue"], g["fills"], strict=True))
            ra = fills.get("risk_averse")
            if ra is None or any(ra > fills[q] for q in M2_QUEUES[1:] if q in fills):
                bad.append((s, day, lat))
    r.add(
        "AC2.4 risk-averse has no more fills than any other queue model, B0 and B1",
        runs is not None and not missing and not bad,
        f"bad {sorted(bad)[:4]}",
    )

    ac2_5_v2(r, train)

    r.add(
        "AC2.6 layering test in tests/leakage",
        "def test_ac2_6_" in read("tests/leakage/test_layering.py"),
    )


def ac2_5_v2(r: Results, train: list[str]) -> None:
    """v2: B0 and B1 have no parameters, so nothing is chosen. selected.yaml says so, and
    v2 B0 and B1 ran on every training day in all 8 cells."""
    sel = yaml.safe_load(read("configs/selected.yaml") or "{}") or {}
    r.add(
        "AC2.5 selected.yaml has v2 B0 and B1 with no parameters",
        sel.get("B0") == {} and sel.get("B1") == {},
        f"B0 {sel.get('B0')}, B1 {sel.get('B1')}",
    )
    m = study_runs("v2_train")
    want = {
        (s, q, lat, d)
        for s in ("B0", "B1")
        for q in M2_QUEUES
        for lat in M2_LATENCIES
        for d in train
    }
    have = set() if m is None else set(m.select("strategy", "queue", "latency", "day").iter_rows())
    r.add(
        "AC2.5 v2 B0 and B1 on every training day in all 8 cells",
        want <= have,
        f"missing {len(want - have)} of {len(want)}",
    )


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


def tag_created() -> datetime | None:
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
    # v2 plans two test-day runs (section 10): the grid, then the random-pull controls at
    # its realised rates. The first run of each is planned; any other is a rerun.
    planned = ("configs/runs/confirmatory.yaml", "configs/runs/confirmatory_controls.yaml")
    firsts = {c: next((m["config_hash"] for m, _ in ordered if m["config"] == c), None)
              for c in planned}  # fmt: skip
    reruns = [m for m, _ in ordered if m["config_hash"] not in firsts.values()]
    unlisted = [m["config_hash"] for m in reruns if m["config_hash"] not in deviations]
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


def m6(r: Results) -> None:
    summary = ROOT / "results" / "summary.json"
    build = ROOT / "paper" / "build"
    page, pdf = build / "paper.md", build / "summary.pdf"
    tracked = bool(
        subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--", "results/summary.json"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    check = subprocess.run(
        ["uv", "run", "python", "paper/check_paper.py"], cwd=ROOT, capture_output=True, text=True
    )
    r.add(
        "AC6.1 paper built from the committed summary.json: no open {{key}}, no literal decimal",
        tracked and page.exists() and check.returncode == 0,
        f"summary.json tracked {tracked}; paper.md {page.exists()}; "
        f"check_paper exit {check.returncode}",
    )
    # make paper writes summary.pdf from summary.json, so a PDF older than it is stale.
    fresh = pdf.exists() and summary.exists() and pdf.stat().st_mtime >= summary.stat().st_mtime
    r.add(
        "AC6.2 one-page PDF built from the same summary.json",
        fresh,
        "paper/build/summary.pdf is newer than results/summary.json" if fresh else "missing or stale",
    )
    heading = "## What I would do with L3 data and real fills"
    built = page.read_text() if page.exists() else ""
    r.add(
        "AC6.3 section on L3 data and real fills",
        heading in read("paper/template.md") and heading in built,
        "in the template and in the built page",
    )
    readme = read("README.md")
    missing = [s for s in ("make data", "make run", "make paper") if s not in readme]
    r.add(
        "AC6.4 README reproduces the study with make data, make run, make paper",
        not missing,
        f"missing {missing}" if missing else "all three in the README",
    )
    lint = subprocess.run(
        ["uv", "run", "pytest", "tests/test_writing.py", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    r.add("AC6.5 writing lint passes on everything", lint.returncode == 0, f"exit {lint.returncode}")


MILESTONES = {"M0": m0, "M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5, "M6": m6}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    name = sys.argv[1].upper()
    fn = MILESTONES.get(name)
    if fn is None:
        print(f"No checks for {name} yet. Write them from SPEC.md and get Ilia's approval first.")
        return 1
    results = Results()
    fn(results)
    return results.report()


if __name__ == "__main__":
    sys.exit(main())
