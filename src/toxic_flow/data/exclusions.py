"""Apply the pre-registered exclusion rules (PREREGISTRATION.md section 2) by script.

Usage: uv run python -m toxic_flow.data.exclusions
Writes docs/data_quality/EXCLUSIONS.md. Rule 1: a file counts as missing only when a GET of
it was answered 404 or 400 twice, at least 24 hours apart, as data/tardis_requests.jsonl
records; 429, 5xx, network errors and HEAD responses never count. Rules 2 and 3 come from
the day's docs/data_quality/<date>.json. No other reason excludes a day.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from toxic_flow.data.split_lock import load_splits
from toxic_flow.data.tardis import DATA_TYPES, LOG_FILE, dataset_url

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / "docs" / "data_quality"
CONVERTED = ROOT / "data" / "converted"
MISSING_STATUSES = {400, 404}


def missing_by_rule_1(log: Path, url: str) -> bool:
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    times = sorted(
        datetime.fromisoformat(r["at"])
        for r in rows
        if r.get("event") == "response"
        and r.get("url") == url
        and r.get("status") in MISSING_STATUSES
    )
    return len(times) >= 2 and times[-1] - times[0] >= timedelta(hours=24)


def excluded_days(days, quality_dir: Path = QUALITY, log: Path = LOG_FILE, converted=CONVERTED):
    """{day: [rule numbers]} for every day that meets at least one rule."""
    found = {}
    for day in days:
        rules = []
        if any(missing_by_rule_1(log, dataset_url(day, t)) for t in DATA_TYPES):
            rules.append(1)
        q = quality_dir / f"{day}.json"
        if q.exists():
            report = json.loads(q.read_text())
            rules += [n for n in (2, 3) if report.get(f"exclusion_rule_{n}")]
        if rules:
            found[day] = rules
    return found


def write_exclusions(found: dict, days: list[str], out: Path, quality_dir: Path = QUALITY) -> Path:
    assessed = [d for d in days if (quality_dir / f"{d}.json").exists() or d in found]
    lines = [
        "# Excluded days",
        "",
        "Written by `uv run python -m toxic_flow.data.exclusions` from the pre-registered rules",
        "in PREREGISTRATION.md section 2. No other reason excludes a day.",
        "",
    ]
    if found:
        lines += ["| Date | Rules |", "|---|---|"]
        lines += [
            f"| {d} | {', '.join(f'rule {n}' for n in rules)} |"
            for d, rules in sorted(found.items())
        ]
    else:
        lines.append("No day meets an exclusion rule.")
    lines += [
        "",
        f"Days assessed so far: {len(assessed)} of {len(days)} ({', '.join(assessed) or 'none'}).",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out


def main() -> None:
    splits = load_splits()
    days = splits["train"] + splits["val"] + splits["test"]
    print(write_exclusions(excluded_days(days), days, QUALITY / "EXCLUSIONS.md"))


if __name__ == "__main__":
    main()
