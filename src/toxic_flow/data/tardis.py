"""Tardis.dev dataset layout for this study: one exchange, one symbol, two data types."""

from datetime import UTC, datetime, timedelta

EXCHANGE = "binance-futures"
SYMBOL = "BTCUSDT"
DATA_TYPES = ("incremental_book_L2", "trades")
API_URL = f"https://api.tardis.dev/v1/exchanges/{EXCHANGE}"


def dataset_url(day: str, data_type: str) -> str:
    y, m, d = day.split("-")
    return f"https://datasets.tardis.dev/v1/{EXCHANGE}/{data_type}/{y}/{m}/{d}/{SYMBOL}.csv.gz"


def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def incidents_on(days: list[str], incidents: list[dict]) -> dict[str, list[dict]]:
    """Map each day to the Tardis incident reports whose [from, to) window overlaps it."""
    hits: dict[str, list[dict]] = {}
    for day in days:
        start = datetime.fromisoformat(day).replace(tzinfo=UTC)
        end = start + timedelta(days=1)
        for inc in incidents:
            if _utc(inc["from"]) < end and _utc(inc["to"]) > start:
                hits.setdefault(day, []).append(inc)
    return hits
