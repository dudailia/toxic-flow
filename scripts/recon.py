#!/usr/bin/env python3
"""Recon: what Tardis says about BTCUSDT, and whether each of the 68 study files exists.

Writes data/recon.json. Usage: uv run python scripts/recon.py

1. GET the Tardis exchange API and keep what it says about BTCUSDT.
2. HEAD every dataset URL (34 dates x 2 data types). HEAD transfers no file data.
3. Train and val dates only: a GET whose body is never read, closed right after the
   response headers, to learn the size. datasets.tardis.dev answers HEAD with 404 even
   for files it serves (see docs/DATA_RECON.md), so HEAD alone gives no size. Every such
   GET goes through the split lock first, so it cannot reach a test date.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from toxic_flow.data.split_lock import assert_allowed, load_splits
from toxic_flow.data.tardis import API_URL, DATA_TYPES, EXCHANGE, SYMBOL, dataset_url, incidents_on

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "recon.json"
USER_AGENT = "toxic-flow-recon/0.1 (+https://github.com/dudailia/toxic-flow)"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def request(url: str, method: str, attempts: int = 4) -> tuple[int, dict]:
    """Status and headers only. The response body is never read."""
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers)
        except (TimeoutError, urllib.error.URLError, ConnectionError):
            # datasets.tardis.dev is slow to answer HEAD; a timeout is not an answer.
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def content_length(headers: dict) -> int | None:
    value = headers.get("Content-Length")
    return int(value) if value is not None else None


def exchange_meta(api: dict, days: list[str]) -> dict:
    sym = SYMBOL.lower()
    datasets = api["datasets"]
    return {
        "id": api["id"],
        "name": api["name"],
        "enabled": api["enabled"],
        "availableSince": api["availableSince"],
        "available_symbol": [s for s in api["availableSymbols"] if s["id"] == sym],
        "datasets": {
            "formats": datasets["formats"],
            "exportedFrom": datasets["exportedFrom"],
            "exportedUntil": datasets["exportedUntil"],
            "symbol": [s for s in datasets["symbols"] if s["id"] == SYMBOL],
        },
        "channelDetails": [
            c for c in api["channelDetails"] if c["name"] in ("depth", "depthSnapshot", "trade")
        ],
        "dataCollectionDetails": api["dataCollectionDetails"],
        "incidentReports": api["incidentReports"],
        "incidents_on_study_dates": incidents_on(days, api["incidentReports"]),
    }


def main() -> None:
    splits = load_splits()
    split_of = {d: name for name, ds in splits.items() for d in ds}
    days = sorted(split_of)

    with urllib.request.urlopen(
        urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT}), timeout=30
    ) as r:
        api = json.load(r)

    files = []
    for day in days:
        for data_type in DATA_TYPES:
            url = dataset_url(day, data_type)
            status, headers = request(url, "HEAD")
            row = {
                "date": day,
                "data_type": data_type,
                "split": split_of[day],
                "url": url,
                "method": "HEAD",
                "status": status,
                "content_length": content_length(headers) if status == 200 else None,
                "checked_at": now(),
            }
            if split_of[day] != "test":
                assert_allowed(day)  # raises on a test date; belt and braces
                get_status, get_headers = request(url, "GET")
                row["get_headers"] = {
                    "status": get_status,
                    "content_length": content_length(get_headers),
                    "x_md5": get_headers.get("x-md5", "").strip('"') or None,
                    "checked_at": now(),
                }
            files.append(row)
            print(row["date"], data_type, status, row.get("get_headers", {}).get("content_length"))
            time.sleep(0.2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    recon = {
        "exchange": EXCHANGE,
        "symbol": SYMBOL,
        "api_url": API_URL,
        "fetched_at": now(),
        "exchange_meta": exchange_meta(api, days),
        "files": files,
    }
    OUT.write_text(json.dumps(recon, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(files)} files")


if __name__ == "__main__":
    main()
