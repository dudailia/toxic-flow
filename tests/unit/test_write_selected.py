"""scripts/write_selected.py on a made-up window run: window scoring, floor, edges."""

import importlib.util
import json
from pathlib import Path

import polars as pl
import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "write_selected.py"
spec = importlib.util.spec_from_file_location("write_selected", SCRIPT)
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


def test_window_scores_decide_and_the_floor_is_reported(tmp_path, monkeypatch):
    days = sorted(ws.load_splits()["train"])
    # (params, full-day BEF, window BEF, window fills)
    cands = [
        ({"name": "B0", "h": 1}, -1.0, -1.0, 5000),
        ({"name": "B0", "h": 13}, -0.5, -0.9, 3000),  # best full day, not best in the window
        ({"name": "B0", "h": 8}, -0.9, -0.8, 4000),
        ({"name": "B1", "gamma": 0.2, "window_s": 1200}, -0.7, -0.7, 500),
        ({"name": "B1", "gamma": 0.8, "window_s": 1200}, -0.6, -0.4, 50),  # under the floor
        ({"name": "B1", "gamma": 0.2, "window_s": 4800}, -0.8, -0.75, 400),
    ]
    rows = [{"day": d, "strategy": p["name"], "params": json.dumps(p, sort_keys=True),
             "queue": "risk_averse", "latency": "high", "fills": f + 100,
             "break_even_fee_bps": full, "sel_fills": f, "sel_break_even_fee_bps": win}
            for d in days for p, full, win, f in cands]  # fmt: skip
    run = tmp_path / "run"
    run.mkdir()
    pl.DataFrame(rows).write_parquet(run / "metrics.parquet")
    (run / "meta.json").write_text(json.dumps({"config": ws.RUN, "commit": "0" * 40}))
    (run / "config.yaml").write_text(yaml.safe_dump({"select_from": "01:20:00"}))
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(ws, "ROOT", tmp_path)
    ws.main(run)
    out = yaml.safe_load((tmp_path / "configs" / "selected.yaml").read_text())
    assert out["B0"] == {"h": 8} and out["B1"] == {"gamma": 0.2, "window_s": 1200}
    assert out["without_fill_floor"]["B1"] == {"gamma": 0.8, "window_s": 1200}
    assert out["without_fill_floor"]["B0"] == {"h": 8}
    assert out["at_edge"] == {"B0": {}, "B1": {"gamma": "low", "window_s": "low"}}
    text = (tmp_path / "docs" / "selection" / "B1_train.md").read_text()
    assert "the floor decided the choice" in text
