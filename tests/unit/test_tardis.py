from toxic_flow.data.tardis import dataset_url, incidents_on


def test_dataset_url_layout():
    assert dataset_url("2024-01-01", "trades") == (
        "https://datasets.tardis.dev/v1/binance-futures/trades/2024/01/01/BTCUSDT.csv.gz"
    )


def test_incident_inside_a_day_is_reported():
    inc = {"from": "2024-03-01T05:00:00.000Z", "to": "2024-03-01T05:10:00.000Z"}
    assert incidents_on(["2024-03-01", "2024-04-01"], [inc]) == {"2024-03-01": [inc]}


def test_incident_spanning_midnight_hits_both_days():
    inc = {"from": "2024-02-29T23:50:00.000Z", "to": "2024-03-01T00:10:00.000Z"}
    assert incidents_on(["2024-03-01"], [inc]) == {"2024-03-01": [inc]}


def test_incident_ending_at_midnight_does_not_hit_next_day():
    inc = {"from": "2024-02-29T23:50:00.000Z", "to": "2024-03-01T00:00:00.000Z"}
    assert incidents_on(["2024-03-01"], [inc]) == {}


def test_ongoing_incident_without_end_counts_as_overlapping():
    inc = {"from": "2024-03-01T05:00:00.000Z", "status": "investigating"}
    assert incidents_on(["2024-03-01", "2024-04-01"], [inc]) == {
        "2024-03-01": [inc],
        "2024-04-01": [inc],
    }


def make_client(tmp_path, fetch, slept=None):
    from toxic_flow.data.tardis import TardisClient

    slept = [] if slept is None else slept
    return TardisClient(
        fetch=fetch,
        state=tmp_path / "wait.json",
        log=tmp_path / "requests.jsonl",
        sleep=slept.append,
        clock=lambda: 1_000_000.0 + sum(slept),
    )


def test_retry_after_as_http_date_is_honoured(tmp_path):
    import urllib.error
    from email.utils import formatdate

    import pytest

    from toxic_flow.data.tardis import StopRequests

    # 1_000_000 + 3600 s, as an HTTP date: one hour, longer than the client will sleep.
    when = formatdate(1_000_000 + 3600, usegmt=True)

    def fetch(url):
        raise urllib.error.HTTPError(url, 429, "busy", {"Retry-After": when}, None)

    c = make_client(tmp_path, fetch)
    with pytest.raises(StopRequests):
        c.open("https://example.test/a")
    with pytest.raises(StopRequests):  # remembered: no second request before that time
        make_client(tmp_path, fetch).open("https://example.test/b")


def test_protocol_error_is_counted(tmp_path):
    import http.client

    import pytest

    from toxic_flow.data.tardis import RequestFailed

    def fetch(url):
        raise http.client.BadStatusLine("garbage")

    c = make_client(tmp_path, fetch)
    with pytest.raises(RequestFailed):
        c.open("https://example.test/a")
    assert c.failures == 1


def test_a_failed_url_is_not_requested_again(tmp_path):
    import pytest

    from toxic_flow.data.tardis import RequestFailed

    calls = []

    def fetch(url):
        calls.append(url)
        raise TimeoutError("slow")

    c = make_client(tmp_path, fetch)
    for _ in range(2):
        with pytest.raises(RequestFailed):
            c.open("https://example.test/a")
    assert calls == ["https://example.test/a"]
    assert c.failures == 1


def test_every_request_is_logged_before_it_is_sent(tmp_path):
    import json
    import urllib.error

    import pytest

    from toxic_flow.data.tardis import RequestFailed, TardisClient, dataset_url

    log = tmp_path / "requests.jsonl"
    seen_before = []

    def fetch(url):
        seen_before.append(log.exists() and url in log.read_text())
        if "trades" in url:
            raise urllib.error.HTTPError(url, 404, "missing", {}, None)
        return io_response()

    client = TardisClient(fetch=fetch, state=tmp_path / "wait.json", log=log)
    client.open(dataset_url("2024-01-01", "incremental_book_L2"))
    with pytest.raises(RequestFailed):
        client.open(dataset_url("2024-01-01", "trades"))
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert seen_before == [True, True]
    assert [(r["event"], r.get("status")) for r in rows] == [
        ("request", None),
        ("response", 200),
        ("request", None),
        ("response", 404),
    ]
    assert all(r["url"].startswith("https://datasets.tardis.dev/") for r in rows)


def io_response():
    import io

    r = io.BytesIO(b"")
    r.status = 200
    return r
