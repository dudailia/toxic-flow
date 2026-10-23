"""Exclusion rules (PREREGISTRATION.md section 2) applied by script, and EXCLUSIONS.md."""

import json

from toxic_flow.data.exclusions import excluded_days, missing_by_rule_1, write_exclusions

URL = "https://datasets.tardis.dev/v1/binance-futures/trades/2024/02/01/BTCUSDT.csv.gz"


def log(tmp_path, rows):
    path = tmp_path / "requests.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_rule_1_needs_two_404_or_400_responses_24_hours_apart(tmp_path):
    def resp(at, status):
        return {"at": at, "event": "response", "url": URL, "status": status}

    assert missing_by_rule_1(log(tmp_path, [resp("2026-10-23T00:00:00+00:00", 404),
                                            resp("2026-10-24T00:00:00+00:00", 400)]), URL)  # fmt: skip
    assert not missing_by_rule_1(log(tmp_path, [resp("2026-10-23T00:00:00+00:00", 404),
                                                resp("2026-10-23T23:00:00+00:00", 404)]), URL)  # fmt: skip
    # 429, 5xx and network errors never count as missing
    assert not missing_by_rule_1(log(tmp_path, [resp("2026-10-23T00:00:00+00:00", 429),
                                                resp("2026-10-25T00:00:00+00:00", 503),
                                                resp("2026-10-27T00:00:00+00:00", "TimeoutError")]), URL)  # fmt: skip


def test_quality_reports_set_rules_2_and_3(tmp_path):
    q = tmp_path / "quality"
    q.mkdir()
    (q / "2024-01-01.json").write_text(
        json.dumps({"date": "2024-01-01", "exclusion_rule_3": False})
    )
    (q / "2024-02-01.json").write_text(json.dumps({"date": "2024-02-01", "exclusion_rule_3": True}))
    found = excluded_days(["2024-01-01", "2024-02-01"], q, log(tmp_path, []), converted=tmp_path)
    assert found == {"2024-02-01": [3]}


def test_exclusions_md_lists_each_excluded_day_with_its_rule(tmp_path):
    out = write_exclusions({"2024-02-01": [3]}, ["2024-01-01", "2024-02-01"], tmp_path / "EX.md")
    text = out.read_text()
    assert "2024-02-01" in text and "rule 3" in text
    assert "| 2024-01-01 |" not in text
