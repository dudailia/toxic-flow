#!/usr/bin/env python3
"""M1 for one day: convert it into the cache, write its data-quality report, market-order
events and OFI contributions, then evict the converted parts unless the disk has room.

Usage: uv run python scripts/prepare_day.py YYYY-MM-DD [...]
       (or as run_config's after_day hook: scripts/run_with_m1.py)

Converted days are a cache of the hashed raw files (data/convert.py): convert_day refuses
to start with less than 12 GB free or with too little memory, records or checks the day's
events SHA-256 in data/manifest.json, and evict_converted deletes the parts after use
unless more than 30 GB is free. One day at a time, nothing else heavy running. Writes
docs/data_quality/<day>.json, data/events/<day>.parquet and
data/converted/<day>/ofi_contributions.npz.
"""

import sys
import time

import numpy as np

from toxic_flow.data.convert import CONVERTED, convert_day, evict_converted
from toxic_flow.data.split_lock import normalise
from toxic_flow.data.validate import QUALITY, write_report
from toxic_flow.signals.ofi import ofi_contributions


def m1(day: str) -> None:
    """The quality report and the OFI contributions from one replay of the converted day;
    skipped when both exist."""
    ofi = CONVERTED / day / "ofi_contributions.npz"
    if (QUALITY / f"{day}.json").exists() and ofi.exists():
        return
    bbo = []
    write_report(day, bbo_out=bbo)
    ts, e = ofi_contributions(bbo[0])
    np.savez_compressed(ofi, ts=ts, e=e)


def main(day: str) -> None:
    day = normalise(day)
    t0 = time.perf_counter()
    convert_day(day)  # split lock, raw hashes, disk and memory guards first
    m1(day)
    evicted = evict_converted(day)
    print(
        QUALITY / f"{day}.json",
        f"{time.perf_counter() - t0:.0f} s",
        "evicted" if evicted else "kept",
    )


if __name__ == "__main__":
    for d in sys.argv[1:]:
        main(d)
