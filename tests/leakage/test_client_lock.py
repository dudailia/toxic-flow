"""TardisClient refuses a test-day dataset URL before prereg-v1, without sending or logging it.

The downloader checks the lock too; this covers any other caller of the client.
"""

import pytest

from toxic_flow.data.split_lock import SplitLockError, tag_published
from toxic_flow.data.tardis import API_URL, TardisClient, dataset_url

pytestmark = pytest.mark.skipif(tag_published(), reason="prereg-v1 is public; lock is open")


def make(tmp_path, calls):
    def fetch(url):
        calls.append(url)
        return url

    return TardisClient(fetch=fetch, state=tmp_path / "wait.json", log=tmp_path / "requests.jsonl")


@pytest.mark.parametrize("data_type", ["incremental_book_L2", "trades"])
def test_client_refuses_test_day_url(tmp_path, data_type):
    calls = []
    with pytest.raises(SplitLockError):
        make(tmp_path, calls).open(dataset_url("2025-07-01", data_type))
    assert calls == []
    assert not (tmp_path / "requests.jsonl").exists()


def test_client_refuses_a_dataset_url_for_a_date_in_no_split(tmp_path):
    calls = []
    with pytest.raises(SplitLockError):
        make(tmp_path, calls).open(dataset_url("2025-07-02", "trades"))
    assert calls == []


def test_client_allows_train_day_and_api_urls(tmp_path):
    calls = []
    client = make(tmp_path, calls)
    client.open(dataset_url("2024-01-01", "trades"))
    client.open(API_URL)
    assert len(calls) == 2
