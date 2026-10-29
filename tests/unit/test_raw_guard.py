"""No code path deletes or moves a raw file, except scripts/restore_raw.py --remove, which
takes training and validation days only (Ilia's disk decision, 2026-10-28).

2024-05-01's book file went missing on 2026-10-26 at 23:00:54. The system log shows it was
removed through macOS System Settings > Storage, not by code (DEVIATIONS.md). This test pins
every call in src/, scripts/ and paper/ that can delete or move a file, with the reason
each one cannot reach data/raw, so a new one fails here until someone has looked at it."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELETE = {"unlink", "rmdir", "rmtree", "remove", "removedirs", "rename", "renames", "move"}

# (file, function, call): why the target is not a raw file.
ALLOWED = {
    # The .part file the downloader streams into; the raw file is placed by os.link.
    ("src/toxic_flow/data/download.py", "download_day", "part.unlink(missing_ok=True)"),
    # data/manifest.json written through a temporary file.
    ("src/toxic_flow/data/download.py", "save_manifest", "os.replace(tmp, path)"),
    ("src/toxic_flow/data/convert.py", "_record_converted", "os.replace(tmp, manifest)"),
    # The converted cache, data/converted/<day> and its staging folder, never data/raw.
    ("src/toxic_flow/data/convert.py", "evict_converted", "(dest / 'convert.json').unlink()"),
    ("src/toxic_flow/data/convert.py", "evict_converted", "(dest / name).unlink()"),
    ("src/toxic_flow/data/convert.py", "evict_converted", "dest.rmdir()"),
    ("src/toxic_flow/data/convert.py", "convert_day", "shutil.rmtree(staging, ignore_errors=True)"),
    ("src/toxic_flow/data/convert.py", "convert_day", "os.replace(f, dest / f.name)"),
    ("src/toxic_flow/data/convert.py", "convert_day", "staging.rmdir()"),
    ("src/toxic_flow/data/convert.py", "convert_day", "os.rename(staging, dest)"),
    # The one path that removes raw files: training and validation days only, each file
    # checked against its pin first (tests/unit/test_restore_raw.py).
    ("scripts/restore_raw.py", "remove", "path.unlink()"),
    ("scripts/restore_raw.py", "remove", "d.rmdir()"),
}


def calls(path: Path):
    """(function, call source) for each call that can delete or move a file."""

    def visit(node, where):
        for c in ast.iter_child_nodes(node):
            w = c.name if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) else where
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
                a, base = c.func.attr, c.func.value
                # Path.replace(target) and os.replace(a, b) move; str.replace(a, b) does not.
                moves = a == "replace" and (
                    (isinstance(base, ast.Name) and base.id == "os") or len(c.args) == 1
                )
                if a in DELETE or moves:
                    yield w, ast.unparse(c)
            yield from visit(c, w)

    yield from visit(ast.parse(path.read_text()), "<module>")


def test_every_delete_or_move_call_is_one_that_cannot_reach_data_raw():
    files = [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/*.py"), *ROOT.glob("paper/*.py")]
    found = {(str(f.relative_to(ROOT)), w, c) for f in files for w, c in calls(f)}
    assert found - ALLOWED == set(), "new delete or move calls: check they cannot reach data/raw"
    assert ALLOWED - found == set(), "listed calls no longer exist: update ALLOWED"


def test_no_shell_rule_in_the_makefile_deletes_or_moves_files():
    rules = (ROOT / "Makefile").read_text()
    assert not any(f"\t{cmd} " in rules or f" {cmd} " in rules for cmd in ("rm", "mv"))
