#!/usr/bin/env python3
"""M1 for one day: convert it into the cache, write its data-quality report, market-order
events and OFI contributions, then evict the converted parts unless the disk has room.

Usage: uv run python scripts/prepare_day.py YYYY-MM-DD

Converted days are a cache of the hashed raw files (data/convert.py): convert_day refuses
to start with less than 15 GB free, records or checks each part's SHA-256 in
data/manifest.json, and evict_converted deletes the parts after use unless more than
30 GB is free. Run one at a time, with nothing else heavy running. Writes
docs/data_quality/<day>.json, data/events/<day>.parquet and
data/converted/<day>/ofi_contributions.npz.
"""

import sys
import time

from toxic_flow.data.convert import convert_day, evict_converted
from toxic_flow.data.split_lock import normalise
from toxic_flow.data.validate import write_report
from toxic_flow.engine.run import ofi_inputs


def main(day: str) -> None:
    day = normalise(day)
    t0 = time.perf_counter()
    convert_day(day)  # split lock, raw hashes and the disk guard first
    report = write_report(day)
    ofi_inputs(day)  # builds data/converted/<day>/ofi_contributions.npz if missing
    evicted = evict_converted(day)
    print(report, f"{time.perf_counter() - t0:.0f} s", "evicted" if evicted else "kept")


if __name__ == "__main__":
    main(sys.argv[1])
