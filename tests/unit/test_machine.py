import resource

from toxic_flow import machine


def test_peak_rss_is_bytes_on_every_platform(monkeypatch):
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    monkeypatch.setattr(machine.sys, "platform", "darwin")
    assert machine.peak_rss_bytes() >= raw  # macOS reports bytes
    monkeypatch.setattr(machine.sys, "platform", "linux")
    assert machine.peak_rss_bytes() >= raw * 1024  # Linux reports KiB
