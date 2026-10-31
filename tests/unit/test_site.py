"""The project page's data (make site-data): every number comes from a committed file."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
BUNDLE = ROOT / "site" / "toxic-flow.json"
SCHEMA = ROOT / "site" / "schema.json"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


@pytest.fixture(scope="module")
def bundle() -> dict:
    return json.loads(BUNDLE.read_text())


def test_the_committed_bundle_is_what_the_script_builds_now(bundle):
    """The trace test, part 1: the script reads only committed sources (it refuses any
    other), so a bundle equal to its output holds no number from anywhere else."""
    from site_data import build

    assert json.loads(json.dumps(build(), sort_keys=True)) == bundle


@pytest.mark.parametrize(
    ("status", "ok"),
    [("", True), ("M  paper/template.md\n", True), (" M paper/template.md\n", False),
     ("MM paper/template.md\n", False)],
)  # fmt: skip
def test_a_source_staged_for_commit_is_read_and_an_unstaged_edit_is_refused(
    monkeypatch, status, ok
):
    """The pre-commit hook builds the bundle while the change is staged, so a staged source
    counts as committed; a working copy that differs from the index never does."""
    import site_data

    out = {"ls-files": "paper/template.md\n", "status": status}
    monkeypatch.setattr(site_data, "git", lambda *a: out[a[0]])
    if ok:
        assert site_data.committed("paper/template.md") == "paper/template.md"
    else:
        with pytest.raises(SystemExit, match="differs from the commit"):
            site_data.committed("paper/template.md")


def numbers(x, path=(), source=None):
    """(path, value, nearest source) for every number in x."""
    if isinstance(x, dict):
        source = x.get("source", source)
        for k, v in x.items():
            if k != "source":
                yield from numbers(v, (*path, k), source)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from numbers(v, (*path, i), source)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield path, x, source


# Sections whose numbers are not results: dates and labels of the design. Everything else,
# the test-day block included, needs a source.
NOT_RESULTS = ("splits", "cells", "runs", "design_history")


def test_every_number_names_committed_results_it_comes_from(bundle):
    """The trace test, part 2: each number sits under a source, and each source is a file
    git tracks, unchanged since the commit."""
    seen = set()
    for path, _, source in numbers(bundle):
        if path[0] in NOT_RESULTS:
            continue
        assert source, f"{'/'.join(map(str, path))} has no source"
        for s in [source] if isinstance(source, str) else source:
            for f in s.split(", "):
                seen.add(f)
    assert seen
    for f in sorted(seen):
        assert git("ls-files", "--", f).stdout.strip(), f"{f} is not tracked"
        assert not git("status", "--porcelain", "--", f).stdout.strip(), f"{f} has changes"
    assert any(f.startswith("results/") and f.endswith("metrics.parquet") for f in seen)


def test_the_v1_block_is_c2_against_b1_from_the_committed_v1_canary_run(bundle):
    """Covered by the trace test above like every section; here also checked against the
    run docs/M4_draft.md reports, recomputed from its committed metrics."""
    import polars as pl

    from toxic_flow.eval import analysis

    v1 = bundle["v1"]
    assert v1["label"] == v1["c2_minus_b1"]["label"] == "v1 design, superseded; failed canary C2"
    src = "results/9eaa1b3d693c/metrics.parquet"
    assert v1["source"] == v1["c2_minus_b1"]["source"] == src
    assert "9eaa1b3d693c" in (ROOT / "docs" / "M4_draft.md").read_text()
    c = analysis.compare(pl.read_parquet(ROOT / src), "C2", "B1")
    got = v1["c2_minus_b1"]
    assert (got["a"], got["b"], got["cell"]) == ("C2", "B1", "risk_averse/high")
    assert got["mean_bp"] == c["mean"] and got["days_positive"] == c["n_positive"]
    assert got["bootstrap_ci_bp"] == list(c["bootstrap_ci"]) and got["t_ci_bp"] == list(c["t_ci"])
    assert got["per_day_bp"] == c["per_day"] and len(got["per_day_bp"]) == 6
    assert got["bootstrap_ci_bp"][1] < 0  # the failure: the oracle lost to B1


def test_every_test_day_value_is_the_committed_summary_s(bundle):
    """The trace test for the test days: each value equals results/summary.json at its key,
    and summary.json names the committed runs it was computed from."""
    t = bundle["test"]
    s = json.loads((ROOT / "results" / "summary.json").read_text())
    assert t["source"] == "results/summary.json"
    assert t["keys"] and t["keys"] == {k: s[k] for k in t["keys"]}
    # The post-hoc numbers (DEVIATIONS.md entry 6) travel with the label that says so.
    assert {"posthoc_sd_bp", "posthoc_mde_bp"} <= set(t["keys"])
    assert t["posthoc_note"] == s["posthoc_note"]
    assert "not part of the pre-registered analysis" in t["posthoc_note"]
    assert t["h1_per_day_bp"] == s["h1"]["primary"]["per_day"]
    assert list(t["h1_per_day_bp"]) == bundle["splits"]["test"]
    assert t["h1_cell_means_bp"] == s["h1"]["cell_means"]
    assert set(t["h1_cell_means_bp"]) == set(bundle["cells"])
    assert t["no_print_share"] == s["no_print_share"]
    assert t["runs"] == s["runs"] and t["runs"]
    for r in t["runs"]:
        assert git("ls-files", "--", f"results/{r['config_hash']}/metrics.parquet").stdout.strip()
    # No test day appears anywhere outside the test block.
    rest = json.dumps({k: v for k, v in bundle.items() if k not in ("test", "splits")})
    assert not [d for d in bundle["splits"]["test"] if d in rest]


def test_the_paper_template_keys_are_all_in_the_bundle(bundle):
    import re

    template = (ROOT / "paper" / "template.md").read_text()
    keys = {k for k in re.findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", template)
            if not k.startswith("pre_")}  # fmt: skip
    assert keys == set(bundle["test"]["keys"])


def test_section_11_sentences_are_word_for_word_with_their_keys(bundle):
    from toxic_flow.eval.bootstrap import STATEMENTS

    rows = bundle["preregistered_conclusions"]["rows"]
    prereg = (ROOT / "PREREGISTRATION.md").read_text()
    assert len(rows) == 7
    for r in rows:
        assert f"| {r['statement']} |" in prereg
    by_key = {r["key"]: r["statement"] for r in rows}
    for k, text in STATEMENTS.items():
        assert by_key[k] == text.format(mean="X", lo="L", hi="U", mde="MDE")


def test_design_history_commits_exist_on_their_dates(bundle):
    for e in bundle["design_history"]:
        if e["commit"] is None:
            continue  # the tag, still to come
        date = git("show", "-s", "--format=%cs", e["commit"]).stdout.strip()
        assert date == e["date"], e


def validate(x, schema, root, path="$"):
    """The part of JSON Schema that site/schema.json uses: type, required, properties,
    additionalProperties, items, minItems, maxItems and $ref."""
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        return validate(x, node, root, path)
    kinds = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
             "null": type(None), "boolean": bool}  # fmt: skip
    if "type" in schema:
        want = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        ok = any(isinstance(x, kinds[w]) and not (w in ("integer", "number") and isinstance(x, bool))
                 for w in want)  # fmt: skip
        assert ok, f"{path}: {type(x).__name__} is not {want}"
    if isinstance(x, dict):
        for k in schema.get("required", []):
            assert k in x, f"{path}: missing {k}"
        props = schema.get("properties", {})
        for k, v in x.items():
            if k in props:
                validate(v, props[k], root, f"{path}.{k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(v, schema["additionalProperties"], root, f"{path}.{k}")
    if isinstance(x, list):
        assert len(x) >= schema.get("minItems", 0), path
        assert len(x) <= schema.get("maxItems", len(x)), path
        for i, v in enumerate(x):
            if "items" in schema:
                validate(v, schema["items"], root, f"{path}[{i}]")


def test_the_bundle_matches_its_schema(bundle):
    schema = json.loads(SCHEMA.read_text())
    validate(bundle, schema, schema)
    with pytest.raises(AssertionError, match="missing"):
        validate({k: v for k, v in bundle.items() if k != "mde"}, schema, schema)


REPLAY = ROOT / "site" / "replay_window.json"


@pytest.fixture(scope="module")
def replay() -> dict:
    return json.loads(REPLAY.read_text())


def test_the_replay_window_is_the_minute_the_rule_fixed_and_under_3_mb(replay):
    assert REPLAY.stat().st_size < 3_000_000
    assert (replay["day"], replay["window_utc"]) == ("2024-06-01", ["12:00:00", "12:01:00"])
    from site_replay import DAY, END, START

    assert (DAY, START, END) == ("2024-06-01", "12:00:00", "12:01:00")
    times = [b["t_ms"] for b in replay["book"]]
    assert len(times) == 600 and all(0 <= t < 60_000 for t in times)
    assert replay["signals"]["t_ms"] == times
    for s in replay["strategies"].values():
        assert [q["t_ms"] for q in s["quotes"]] == times  # the book each quote was set from
    assert all(0 <= t["t_ms"] < 60_000 for t in replay["trades"])


def test_each_strategy_in_the_replay_reproduces_its_committed_day_result(replay):
    """The trace test for the replay: the whole day behind the minute equals the committed
    training-day result, so the minute shown comes from runs already reported."""
    import polars as pl

    assert set(replay["strategies"]) == {"B1", "B3", "F"}
    for name, s in replay["strategies"].items():
        src = s["day_result"]["reproduces"]
        assert git("ls-files", "--", src).stdout.strip(), src
        m = pl.read_parquet(ROOT / src)
        m = m if "label" in m.columns else m.with_columns(label=pl.col("strategy"))
        label = "F_h0.1" if name == "F" else name
        r = m.filter((pl.col("label") == label) & (pl.col("day") == "2024-06-01")
                     & (pl.col("queue") == "risk_averse") & (pl.col("latency") == "high"))  # fmt: skip
        assert r.height == 1
        assert r["fills"][0] == s["day_result"]["fills"]
        assert r["break_even_fee_bps"][0] == pytest.approx(
            s["day_result"]["break_even_fee_bps"], abs=1e-9
        )


def test_replay_fills_are_simulated_and_pulls_match_the_quotes(replay):
    for s in replay["strategies"].values():
        assert all(f["simulated"] is True for f in s["fills"])
        quotes = {q["t_ms"]: q for q in s["quotes"]}
        for p in s["pulls"]:
            pulled = [q for t, q in quotes.items() if p["start_ms"] <= t < p["end_ms"]]
            assert pulled and all(q[p["side"]] is None for q in pulled)
    assert replay["strategies"]["B1"]["pulls"] == []  # B1 never pulls


def test_replay_book_levels_are_ordered_and_uncrossed(replay):
    for b in replay["book"]:
        bids, asks = [p for p, _ in b["bids"]], [p for p, _ in b["asks"]]
        assert 1 <= len(bids) <= 5 and 1 <= len(asks) <= 5
        assert bids == sorted(bids, reverse=True) and asks == sorted(asks)
        assert bids[0] < asks[0]
    lam = replay["signals"]
    assert min(lam["hawkes_lambda_b"] + lam["hawkes_lambda_s"]) > 0
