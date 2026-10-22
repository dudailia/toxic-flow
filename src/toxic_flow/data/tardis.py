"""Tardis.dev dataset layout for this study: one exchange, one symbol, two data types."""

import http.client
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from toxic_flow.data.split_lock import assert_allowed

EXCHANGE = "binance-futures"
SYMBOL = "BTCUSDT"
DATA_TYPES = ("incremental_book_L2", "trades")
API_URL = f"https://api.tardis.dev/v1/exchanges/{EXCHANGE}"
USER_AGENT = "toxic-flow/0.1 (+https://github.com/dudailia/toxic-flow)"
WAIT_FILE = Path(__file__).resolve().parents[3] / "data" / "tardis_wait.json"
# Append-only and committed: every request this repo sends to tardis.dev, written before it
# goes out. scripts/check_milestone.py M0 fails on any test-day URL in it.
LOG_FILE = Path(__file__).resolve().parents[3] / "data" / "tardis_requests.jsonl"
DATASET_DATE = re.compile(r"datasets\.tardis\.dev/v1/[^/]+/[^/]+/(\d{4})/(\d{2})/(\d{2})/")


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
            # An incident with no end yet is still going on.
            to = _utc(inc["to"]) if inc.get("to") else datetime.max.replace(tzinfo=UTC)
            if _utc(inc["from"]) < end and to > start:
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

    def __init__(
        self,
        fetch=_urlopen,
        state: Path | None = None,
        log: Path | None = None,
        sleep=time.sleep,
        clock=time.time,
    ):
        # Looked up at call time, so tests/conftest.py can point every test elsewhere.
        self.state, self.log = state or WAIT_FILE, log or LOG_FILE
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.failures = 0
        self.failed_urls: set[str] = set()

    def _retry_after_s(self, value: str | None) -> float | None:
        """Retry-After as seconds from now. RFC 9110 allows seconds or an HTTP date; a value
        that is neither counts as a long wait, so it stops the run rather than being ignored."""
        if not value:
            return None
        if value.strip().isdigit():
            return float(value)
        try:
            return parsedate_to_datetime(value).timestamp() - self.clock()
        except (TypeError, ValueError):
            return self.MAX_WAIT_S + 1.0

    def _not_before(self) -> float:
        return json.loads(self.state.read_text())["not_before"] if self.state.exists() else 0.0

    def open(self, url: str):
        """The open response for url. Raises RequestFailed, StopRequests or SplitLockError."""
        day = DATASET_DATE.search(url)
        if day:
            assert_allowed("-".join(day.groups()))  # a test-day file is refused before anything
        if url in self.failed_urls:
            raise RequestFailed(f"{url} already failed in this run; not requested again")
        if self.failures >= self.MAX_FAILURES:
            raise StopRequests(f"{self.failures} failures already in this run")
        wait = self._not_before() - self.clock()
        if wait > self.MAX_WAIT_S:
            when = datetime.fromtimestamp(self._not_before(), UTC).isoformat(timespec="seconds")
            raise StopRequests(f"tardis.dev asked for no requests before {when}")
        if wait > 0:
            self.sleep(wait)
        self._record("request", url)
        try:
            response = self.fetch(url)
        except urllib.error.HTTPError as e:
            self._record("response", url, e.code)
            retry_after = self._retry_after_s((e.headers or {}).get("Retry-After"))
            self.failed(f"HTTP {e.code} for {url}", retry_after, url)
        except (OSError, http.client.HTTPException) as e:  # timeouts, resets, bad responses
            self._record("response", url, type(e).__name__)
            self.failed(f"{type(e).__name__} for {url}: {e}", url=url)
        self._record("response", url, getattr(response, "status", None))
        return response

    def _record(self, event: str, url: str, status=None) -> None:
        row = {"at": datetime.fromtimestamp(self.clock(), UTC).isoformat(timespec="seconds")}
        row |= {"event": event, "url": url}
        if event == "response":
            row["status"] = status
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log, "a") as f:
            f.write(json.dumps(row) + "\n")

    def failed(self, reason: str, retry_after: float | None = None, url: str | None = None):
        """Count a failure, set when the next request may go, and raise."""
        self.failures += 1
        if url is not None:
            self.failed_urls.add(url)
        wait = retry_after if retry_after is not None else self.PAUSE_S
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps({"not_before": self.clock() + wait, "reason": reason}))
        if self.failures >= self.MAX_FAILURES:
            raise StopRequests(f"stopped after {self.failures} failures; last: {reason}")
        if wait > self.MAX_WAIT_S:
            raise StopRequests(f"{reason}; Retry-After {wait:.0f} s")
        raise RequestFailed(reason)
