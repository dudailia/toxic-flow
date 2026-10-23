#!/usr/bin/env python3
"""M1 for one day without converted files on disk: convert in memory, then write the
data-quality report, the market-order events and the OFI contributions.

Usage: uv run python scripts/prepare_day.py YYYY-MM-DD

Used when the disk cannot hold every converted day (Q4): the parts live only in this
process, so nothing under data/ is overwritten or removed. Writes
docs/data_quality/<day>.json, data/events/<day>.parquet, and
data/converted/<day>/ofi_contributions.npz with memory_convert.json (the conversion info;
not convert.json, which marks parts on disk). The raw files are checked against
data/manifest.json first, as convert_day does.
"""

import json
import sys
import time

import numpy as np

from toxic_flow.data.convert import CONVERTED, convert_day_in_memory
from toxic_flow.data.split_lock import normalise
from toxic_flow.data.validate import write_report
from toxic_flow.signals.ofi import ofi_contributions


def main(day: str) -> None:
    day = normalise(day)
    t0 = time.perf_counter()
    parts, info = convert_day_in_memory(day)  # split lock and raw hashes checked first
    info["conversion_seconds"] = round(time.perf_counter() - t0, 1)
    bbo = []
    report = write_report(day, parts=parts, info=info, bbo_out=bbo)
    ts, e = ofi_contributions(bbo[0])
    out = CONVERTED / day
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "ofi_contributions.npz", ts=ts, e=e)
    keep = {k: v for k, v in info.items() if k != "cuts"} | {"in_memory": True}
    (out / "memory_convert.json").write_text(json.dumps(keep, indent=2, default=int) + "\n")
    print(report, f"{time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1])
