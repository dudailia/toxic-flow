"""AC2.6: no import path from toxic_flow.strategies or toxic_flow.signals into toxic_flow.eval.
Markouts and other forward-looking code live only in eval. Pending: to move into
tests/leakage/ (protected) by Ilia."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
FORBIDDEN = "toxic_flow.eval"
RESTRICTED = ("toxic_flow.strategies", "toxic_flow.signals")


def module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
    return ".".join(parts)


def import_graph(src: Path = SRC) -> dict[str, set[str]]:
    """Each toxic_flow module and the toxic_flow modules it imports (any form)."""
    graph = {}
    for path in src.rglob("*.py"):
        mod = module_name(path)
        deps = set()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                deps |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:  # relative import: resolve against this package
                    pkg = (
                        mod.split(".")[: -node.level]
                        if not path.name == "__init__.py"
                        else mod.split(".")
                    )
                    base = ".".join([*pkg, base] if base else pkg)
                deps.add(base)
                deps |= {f"{base}.{a.name}" for a in node.names}
        graph[mod] = {d for d in deps if d.startswith("toxic_flow")}
    return graph


def path_to(graph: dict[str, set[str]], start: str, target: str) -> list[str] | None:
    """An import chain from start to target or one of its submodules, if there is one."""
    seen, stack = set(), [[start]]
    while stack:
        chain = stack.pop()
        node = chain[-1]
        if node == target or node.startswith(target + "."):
            return chain
        if node in seen:
            continue
        seen.add(node)
        for nxt in graph.get(node, ()):
            stack.append([*chain, nxt])
    return None


def test_ac2_6_no_import_path_from_strategies_or_signals_into_eval():
    graph = import_graph()
    starts = [m for m in graph if m.startswith(RESTRICTED)]
    assert starts, "found no strategy or signal modules"
    chains = [c for c in (path_to(graph, m, FORBIDDEN) for m in starts) if c]
    assert not chains, chains


def test_the_layering_check_finds_an_indirect_path():
    graph = {
        "toxic_flow.strategies.x": {"toxic_flow.data.y"},
        "toxic_flow.data.y": {"toxic_flow.eval.markouts"},
    }
    assert path_to(graph, "toxic_flow.strategies.x", FORBIDDEN) == [
        "toxic_flow.strategies.x",
        "toxic_flow.data.y",
        "toxic_flow.eval.markouts",
    ]
