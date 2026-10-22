"""Venue facts per study date, from configs/venue.yaml. See that file for the sources."""

from functools import cache
from pathlib import Path

import yaml

from toxic_flow.data.split_lock import normalise

VENUE = Path(__file__).resolve().parents[3] / "configs" / "venue.yaml"
FIELDS = ("tick_size", "lot_size", "min_notional", "maker_fee_bps", "taker_fee_bps", "source")


@cache
def _by_date() -> dict:
    return {str(k): v for k, v in yaml.safe_load(VENUE.read_text())["by_date"].items()}


def venue_for(day: str) -> dict:
    return _by_date()[normalise(day)]
