"""Tardis.dev dataset layout for this study: one exchange, one symbol, two data types."""

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

EXCHANGE = "binance-futures"
SYMBOL = "BTCUSDT"
DATA_TYPES = ("incremental_book_L2", "trades")
API_URL = f"https://api.tardis.dev/v1/exchanges/{EXCHANGE}"
USER_AGENT = "toxic-flow/0.1 (+https://github.com/dudailia/toxic-flow)"
WAIT_FILE = Path(__file__).resolve().parents[3] / "data" / "tardis_wait.json"


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


class RequestFailed(RuntimeError):
    """One request failed; it is counted and not retried in this run."""


class StopRequests(RuntimeError):
    """No more requests to tardis.dev in this run."""


def _urlopen(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=60)


class TardisClient:
    """The only way this repo talks to tardis.dev: one request at a time, no retry loops.

    After a failure the next request waits for Retry-After (or PAUSE_S without one). A
    wait longer than MAX_WAIT_S stops the run instead, and the time is kept in the state
    file so a new run makes no request before it. The run stops at the third failure.
    A failed URL is not requested again in the same run.
    """

    MAX_FAILURES = 3
    MAX_WAIT_S = 300
    PAUSE_S = 10

    def __init__(self, fetch=_urlopen, state: Path = WAIT_FILE, sleep=time.sleep, clock=time.time):
        self.fetch, self.state, self.sleep, self.clock = fetch, state, sleep, clock
        self.failures = 0

    def _not_before(self) -> float:
        return json.loads(self.state.read_text())["not_before"] if self.state.exists() else 0.0

    def open(self, url: str):
        """The open response for url. Raises RequestFailed or StopRequests."""
        if self.failures >= self.MAX_FAILURES:
            raise StopRequests(f"{self.failures} failures already in this run")
        wait = self._not_before() - self.clock()
        if wait > self.MAX_WAIT_S:
            when = datetime.fromtimestamp(self._not_before(), UTC).isoformat(timespec="seconds")
            raise StopRequests(f"tardis.dev asked for no requests before {when}")
        if wait > 0:
            self.sleep(wait)
        try:
            return self.fetch(url)
        except urllib.error.HTTPError as e:
            retry_after = (e.headers or {}).get("Retry-After")
            self.failed(f"HTTP {e.code} for {url}", int(retry_after) if retry_after else None)
        except OSError as e:  # timeouts, refused or reset connections, DNS
            self.failed(f"{type(e).__name__} for {url}: {e}")

    def failed(self, reason: str, retry_after: int | None = None) -> None:
        """Count a failure, set when the next request may go, and raise."""
        self.failures += 1
        wait = retry_after if retry_after is not None else self.PAUSE_S
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps({"not_before": self.clock() + wait, "reason": reason}))
        if self.failures >= self.MAX_FAILURES:
            raise StopRequests(f"stopped after {self.failures} failures; last: {reason}")
        if wait > self.MAX_WAIT_S:
            raise StopRequests(f"{reason}; Retry-After {wait} s")
        raise RequestFailed(reason)
