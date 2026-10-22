"""The downloader and converter consult the split lock before touching a test-day URL or file.

These run against the project's own repo, where prereg-v1 does not exist yet, so every
test date must be refused. Once Ilia pushes the tag the lock opens and these tests skip;
from then on the M5 check on downloaded_at carries the evidence.
"""

import pytest

from toxic_flow.data.download import download_day
from toxic_flow.data.split_lock import SplitLockError, tag_published

pytestmark = pytest.mark.skipif(tag_published(), reason="prereg-v1 is public; lock is open")


def test_download_refuses_test_day_without_network(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        raise AssertionError("network reached for a test day")

    with pytest.raises(SplitLockError):
        download_day("2025-07-01", raw_dir=tmp_path, manifest=tmp_path / "m.json", fetch=fetch)
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_convert_refuses_test_day(tmp_path):
    from toxic_flow.data.convert import convert_day

    with pytest.raises(SplitLockError):
        convert_day("2025-07-01", raw_dir=tmp_path, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []
