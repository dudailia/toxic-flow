#!/usr/bin/env python3
"""Market-order events for a day from the raw trades alone (M1, SPEC.md AC1.4 and AC1.5).

Usage: uv run python scripts/events_from_raw.py YYYY-MM-DD [...]

The events need only the raw trades and the day's local-timestamp offset, which is a
minimum over both raw files and is streamed here in chunks, so a day never sits in memory
(Q4: no room on disk for converted days, and none in memory for a full conversion).
convert_parts derives the same offset as -min(local - exch) when that is negative.
The raw files are checked against data/manifest.json first.
"""

import json
import sys

from toxic_flow.data.convert import min_feed_latency_ns
from toxic_flow.data.download import MANIFEST, RAW, load_manifest, sha256_file
from toxic_flow.data.split_lock import assert_allowed, normalise
from toxic_flow.data.tardis import DATA_TYPES
from toxic_flow.events.market_orders import EVENTS, build_day


def main(day: str) -> dict:
    assert_allowed(day)
    day = normalise(day)
    pinned = {(e["date"], e["data_type"]): e for e in load_manifest(MANIFEST)}
    for t in DATA_TYPES:
        path, entry = RAW / day / f"{t}.csv.gz", pinned.get((day, t))
        if entry is None or sha256_file(path) != entry["sha256"]:
            raise SystemExit(f"{path} is missing or does not match data/manifest.json")
    min_lat = min_feed_latency_ns(day)
    offset = -min_lat if min_lat < 0 else 0
    stats = build_day(day, offset_ns=offset)
    info = {"date": day, "min_feed_latency_ns": min_lat, **stats}
    (EVENTS / f"{day}.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(json.dumps(main(d)))
