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
import re
import subprocess
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

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
        leaked = [
            p.relative_to(ROOT).as_posix()
            for p in data_dir.rglob("*")
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


MILESTONES = {"M0": m0}


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
