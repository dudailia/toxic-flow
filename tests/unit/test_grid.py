from toxic_flow.engine.grid import config_hash, expand

CFG = {
    "name": "t",
    "days": ["2024-01-01"],
    "strategies": [{"name": "B0", "h": 1}, {"name": "B1", "gamma": 0.05, "window_s": 600}],
    "queue_models": ["risk_averse", "power3", "power2", "log"],
    "latencies": ["low", "high"],
}


def test_expand_covers_every_strategy_queue_model_latency_and_day():
    cells = expand(CFG)
    assert len(cells) == 2 * 4 * 2
    assert {(c["strategy"]["name"], c["queue"], c["latency"]) for c in cells} == {
        (s, q, lat) for s in ("B0", "B1") for q in CFG["queue_models"] for lat in ("low", "high")
    }


def test_zero_latency_only_when_asked():
    assert not any(c["latency"] == "zero" for c in expand(CFG))
    assert sum(c["latency"] == "zero" for c in expand({**CFG, "latencies": ["low", "zero"]})) == 8


def test_config_hash_ignores_key_order_and_changes_with_content():
    assert config_hash(CFG) == config_hash(dict(reversed(list(CFG.items()))))
    assert config_hash(CFG) != config_hash({**CFG, "days": ["2024-02-01"]})


def test_a_strategy_can_name_its_own_cells():
    # Canaries run only in the primary cell and C3 only at zero latency, inside the one
    # confirmatory grid (SPEC.md AC5.3).
    cfg = {
        **CFG,
        "strategies": [
            *CFG["strategies"],
            {"name": "C1", "cells": [["risk_averse", "high"]]},
            {"name": "B3", "cells": [["risk_averse", "zero"]]},
        ],
    }
    cells = [(c["strategy"]["name"], c["queue"], c["latency"]) for c in expand(cfg)]
    assert len(cells) == 2 * 8 + 2
    assert ("C1", "risk_averse", "high") in cells and ("B3", "risk_averse", "zero") in cells
