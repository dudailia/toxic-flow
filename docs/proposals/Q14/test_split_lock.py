"""The test-day lock refuses a test date until prereg-v1 is an annotated tag on the local
repo and on the origin named in configs/repo.yaml, with the same hash on both.

Each test builds a throwaway repo with a bare repo as its origin, so no test touches the
project's own tags or remote.
"""

import subprocess
from datetime import date

import pytest

from toxic_flow.data.split_lock import SplitLockError, assert_allowed, tag_published

TEST_DAY = "2025-07-01"
TRAIN_DAY = "2024-01-01"


def git(repo, *args):
    cfg = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    cfg += ["-c", "tag.gpgsign=false"]
    subprocess.run(["git", *cfg, "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "--bare", "-q", str(remote))
    git(tmp_path, "init", "-q", str(work))
    (work / "f.txt").write_text("x\n")
    git(work, "add", "f.txt")
    git(work, "commit", "-q", "-m", "init")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-q", "origin", "HEAD")
    (work / "configs").mkdir()
    (work / "configs" / "repo.yaml").write_text(f"origin: {remote}\n")
    return work


def tag(repo, message="pre-registration"):
    git(repo, "tag", "-a", "prereg-v1", "-m", message)


def test_no_tag_refuses_test_day(repo):
    assert not tag_published(repo)
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_local_tag_only_refuses_test_day(repo):
    tag(repo)
    assert not tag_published(repo)
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_tag_on_both_allows_test_day(repo):
    tag(repo)
    git(repo, "push", "-q", "origin", "prereg-v1")
    assert tag_published(repo)
    assert assert_allowed(TEST_DAY, repo=repo) == "test"


def test_train_and_val_days_allowed_without_tag(repo):
    assert assert_allowed(TRAIN_DAY, repo=repo) == "train"
    assert assert_allowed("2025-01-01", repo=repo) == "val"


def test_missing_remote_refuses(repo):
    tag(repo)
    git(repo, "push", "-q", "origin", "prereg-v1")
    git(repo, "remote", "remove", "origin")
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_local_tag_differs_from_remote_refuses(repo):
    # A tag re-created locally after the push no longer proves what was published.
    tag(repo)
    git(repo, "push", "-q", "origin", "prereg-v1")
    git(repo, "tag", "-d", "prereg-v1")
    tag(repo, message="re-created")
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


@pytest.mark.parametrize("day", ["2025-07-01T00:00:00", "20250701", date(2025, 7, 1)])
def test_other_spellings_of_a_test_date_refused(repo, day):
    with pytest.raises(SplitLockError):
        assert_allowed(day, repo=repo)


@pytest.mark.parametrize("day", ["2025-07-02", "not-a-date"])
def test_date_outside_every_split_refused(repo, day):
    with pytest.raises(SplitLockError):
        assert_allowed(day, repo=repo)


def test_lightweight_tag_refuses_test_day(repo):
    git(repo, "tag", "prereg-v1")  # no -a: points at the commit, no tag object, no date
    git(repo, "push", "-q", "origin", "prereg-v1")
    assert not tag_published(repo)
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_origin_other_than_the_configured_repo_refuses(repo, tmp_path):
    # The tag is on a remote with the same hash, but not the one configs/repo.yaml names.
    other = tmp_path / "other.git"
    git(tmp_path, "init", "--bare", "-q", str(other))
    tag(repo)
    git(repo, "remote", "set-url", "origin", str(other))
    git(repo, "push", "-q", "origin", "HEAD", "prereg-v1")
    assert not tag_published(repo)
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_remote_tag_replaced_with_another_object_refuses(repo, tmp_path):
    tag(repo)
    git(repo, "push", "-q", "origin", "prereg-v1")
    other = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    git(other, "tag", "-f", "-a", "prereg-v1", "-m", "replaced")
    git(other, "push", "-q", "-f", "origin", "prereg-v1")
    assert not tag_published(repo)
    with pytest.raises(SplitLockError):
        assert_allowed(TEST_DAY, repo=repo)


def test_missing_repo_config_refuses(repo):
    tag(repo)
    git(repo, "push", "-q", "origin", "prereg-v1")
    (repo / "configs" / "repo.yaml").unlink()
    assert not tag_published(repo)
