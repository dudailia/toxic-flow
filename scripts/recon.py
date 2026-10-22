#!/usr/bin/env python3
"""Recon: what the Tardis exchange API says about BTCUSDT and the study dates.

Writes data/recon.json. Usage: uv run python scripts/recon.py

One request: GET the Tardis exchange API, through TardisClient. No request goes to any
dataset URL. HEAD answers 404 for every file on datasets.tardis.dev (docs/DATA_RECON.md),
and test-day URLs get no request of any kind (SPEC.md AC0.1, changed 2026-10-22). File
sizes are recorded in M1 from the downloads (AC1.6).

The per-file records of the earlier recon (HEAD on all 68 files, header-only GET on train
and val files, sent on 2026-10-22 before that change) are carried over unchanged, so the
record of every request made stays in the file.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from toxic_flow.data.split_lock import load_splits
from toxic_flow.data.tardis import API_URL, EXCHANGE, SYMBOL, TardisClient, incidents_on

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "recon.json"


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
    days = sorted(d for ds in load_splits().values() for d in ds)
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    with TardisClient().open(API_URL) as r:
        api = json.load(r)
    recon = {
        "exchange": EXCHANGE,
        "symbol": SYMBOL,
        "api_url": API_URL,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "exchange_meta": exchange_meta(api, days),
        "files": previous.get("files", []),
    }
    OUT.write_text(json.dumps(recon, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}; carried over {len(recon['files'])} file records")


if __name__ == "__main__":
    main()
