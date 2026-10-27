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


# Sections whose numbers are not results: dates and labels of the design, and the count of
# test days. Everything else needs a source.
NOT_RESULTS = ("splits", "cells", "runs", "design_history", "test")


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


def test_every_test_day_value_is_null(bundle):
    t = bundle["test"]
    assert t["keys"] and all(v is None for v in t["keys"].values())
    assert list(t["h1_per_day_bp"]) == bundle["splits"]["test"]
    assert all(v is None for v in t["h1_per_day_bp"].values())
    assert set(t["h1_cell_means_bp"]) == set(bundle["cells"])
    assert [p for p, _, _ in numbers(t)] == []
    # No test day appears anywhere outside the null placeholders.
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
