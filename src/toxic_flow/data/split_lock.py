"""Test-day lock. Every download goes through assert_allowed before a URL is opened.

A test date is allowed only once the annotated tag prereg-v1 exists locally and on the
public remote, and both point at the same tag object. The local tag alone proves nothing:
anyone can create one at any time. The public tag has a push time on GitHub that a
reader can check against downloaded_at in data/manifest.json.

Any failure to ask git (no remote, no network, git error) counts as "not published":
the lock fails closed.
"""

import subprocess
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPLITS = ROOT / "configs" / "splits.yaml"
TAG = "prereg-v1"


class SplitLockError(RuntimeError):
    pass


def load_splits(path: Path = SPLITS) -> dict[str, list[str]]:
    cfg = yaml.safe_load(path.read_text())
    return {name: [str(d) for d in cfg[name]] for name in ("train", "val", "test")}


def normalise(day: str | date) -> str:
    # One canonical spelling, so "20250701" or "2025-07-01T00:00" cannot slip past a
    # string comparison with the test list.
    if isinstance(day, datetime):
        return day.date().isoformat()
    if isinstance(day, date):
        return day.isoformat()
    return datetime.fromisoformat(day.strip()).date().isoformat()


def split_of(day: str | date) -> str:
    d = normalise(day)
    for name, days in load_splits().items():
        if d in days:
            return name
    raise KeyError(d)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, timeout=60
    )
    return out.stdout


def tag_published(repo: Path = ROOT, tag: str = TAG) -> bool:
    try:
        if _git(repo, "tag", "--list", tag).strip() != tag:
            return False
        local_id = _git(repo, "rev-parse", f"refs/tags/{tag}").strip()
        remote = _git(repo, "ls-remote", "--tags", "origin", tag)
    except (subprocess.SubprocessError, OSError):
        return False
    remote_ids = [
        line.split("\t")[0] for line in remote.splitlines() if line.endswith(f"\trefs/tags/{tag}")
    ]
    return remote_ids == [local_id]


def assert_allowed(day: str | date, repo: Path = ROOT) -> str:
    """Return the split of day, or raise SplitLockError if it may not be loaded."""
    try:
        split = split_of(day)
    except (KeyError, ValueError) as e:
        raise SplitLockError(f"{day!r} is not a date in configs/splits.yaml") from e
    if split == "test" and not tag_published(repo):
        raise SplitLockError(
            f"{normalise(day)} is a test day and {TAG} is not on both the local repo and "
            "origin. Test days stay locked until Ilia pushes the tag."
        )
    return split
