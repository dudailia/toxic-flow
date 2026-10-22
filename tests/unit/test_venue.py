import json
from pathlib import Path

import pytest

from toxic_flow.data.split_lock import load_splits
from toxic_flow.data.venue import FIELDS, venue_for

CONVERTED = Path(__file__).resolve().parents[2] / "data" / "converted"
ALL_DAYS = [d for days in load_splits().values() for d in days]


@pytest.mark.parametrize("day", ALL_DAYS)
def test_every_study_date_has_every_field(day):
    v = venue_for(day)
    assert all(v.get(k) not in (None, "") for k in FIELDS)
    assert v["source"]["spec_before"].startswith("https://")


def test_unknown_date_raises():
    with pytest.raises(KeyError):
        venue_for("2024-01-02")


@pytest.mark.parametrize(
    "info", sorted(CONVERTED.glob("*/convert.json")), ids=lambda p: p.parent.name
)
def test_inferred_tick_and_lot_match_venue(info):
    data = json.loads(info.read_text())
    v = venue_for(data["date"])
    assert data["inferred"]["tick_size"] == pytest.approx(v["tick_size"])
    assert data["inferred"]["lot_size"] == pytest.approx(v["lot_size"])
