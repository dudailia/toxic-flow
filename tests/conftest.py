"""Every test gets its own Tardis wait file and request log, so no test can write to the
real data/tardis_wait.json or data/tardis_requests.jsonl."""

import pytest


@pytest.fixture(autouse=True)
def private_tardis_files(tmp_path, monkeypatch):
    import toxic_flow.data.tardis as tardis

    monkeypatch.setattr(tardis, "WAIT_FILE", tmp_path / "tardis_wait.json")
    monkeypatch.setattr(tardis, "LOG_FILE", tmp_path / "tardis_requests.jsonl")
