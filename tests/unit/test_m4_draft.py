"""scripts/m4_draft.py on made-up results: the draft choice, then the report sections."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from toxic_flow.data.split_lock import load_splits

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "m4_draft.py"
spec = importlib.util.spec_from_file_location("m4_draft", SCRIPT)
m4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m4)

RNG = np.random.default_rng(0)


def rows(days, label, params, bef, latency="high", fills=500):
    name = label.split("_")[0]
    p = json.dumps({"name": name, **params}, sort_keys=True)
    return [{"day": d, "strategy": name, "label": label, "params": p, "queue": "risk_averse",
             "latency": latency, "fills": fills, "break_even_fee_bps": bef + RNG.normal(0, 0.05),
             "gross_pnl": bef, "traded_notional": 1e4}
            for d in days]  # fmt: skip


def run(tmp: Path, name: str, config: str, frame: list[dict]) -> Path:
    d = tmp / name
    d.mkdir()
    pl.DataFrame(frame).write_parquet(d / "metrics.parquet")
    meta = {"config": f"configs/runs/{config}.yaml", "config_hash": name, "commit": "0" * 40}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


def test_select_then_report(tmp_path, monkeypatch):
    val, train = m4.kept("val"), m4.kept("train")
    (tmp_path / "configs").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "configs" / "selected.yaml").write_text(
        yaml.safe_dump({"B0": {"h": 5}, "B1": {"gamma": 0.2, "window_s": 1200}})
    )
    monkeypatch.setattr(m4, "ROOT", tmp_path)
    monkeypatch.setattr(m4, "DRAFT_SELECTED", tmp_path / "docs" / "M4_draft_selected.yaml")

    tune = []
    for c in (0.0, 1.0):
        tune += rows(val, "B2", {"c": c, "d": 0.0, "ofi_window_s": 5.0}, -0.7 + 0.2 * c)
        tune += rows(val, "B2b", {"c": c, "d": 0.0, "tau_s": 5.0}, -0.7 - 0.2 * c)
        tune += rows(val, "B3", {"c": c, "d": 0.5}, -0.7 + 0.1 * c)
    m4.cmd_select(run(tmp_path, "tune", "tune_val", tune))
    draft = yaml.safe_load(m4.DRAFT_SELECTED.read_text())
    assert draft["B1"] == {"gamma": 0.2, "window_s": 1200}
    assert draft["B2"]["c"] == 1.0 and draft["B2b"]["c"] == 0.0 and draft["B3"]["c"] == 1.0

    b3 = {"c": 1.0, "d": 0.5}
    can = (rows(val, "B1", {}, -0.7) + rows(val, "B2b", {"c": 0.0}, -0.7)
           + rows(val, "B3", b3, -0.6) + rows(val, "B3", b3, -0.4, latency="zero")
           + rows(val, "C1", b3, -0.7) + rows(val, "C2", {}, 5.0)
           + rows(val, "C4_x10", b3, -0.65) + rows(val, "C4_x0.1", b3, -0.65)
           + rows(val, "B3_c0", {"c": 0.0, "d": 0.5}, -0.7)
           + rows(val, "C1_c0", {"c": 0.0, "d": 0.5}, -0.7))  # fmt: skip
    tr = rows(train, "B2b", {"c": 0.0}, -0.7) + rows(train, "B3", b3, -0.6)
    m4.cmd_report(
        tmp_path / "tune",
        run(tmp_path, "can", "canaries_val_draft", can),
        run(tmp_path, "tr", "mde_train_draft", tr),
    )
    text = (tmp_path / "docs" / "M4_draft.md").read_text()
    n = len(load_splits()["test"])
    for part in ("### B2b", "Pooled BEF bp", "| s, bp |", "C2 - B1", "C1 with c = 0 - B1", "AC4.2", "C4_x10 - B3",
                 f"n = {n} test days"):  # fmt: skip
        assert part in text, part
    assert "AC4.2, C2 beats B1 by more than 3 x MDE: passes." in text


def test_identical_b3_and_b2b_are_named_as_the_reason_for_a_zero_s(tmp_path):
    days = m4.kept("val")
    same = rows(days, "B2b", {"c": 0.0, "d": 0.0}, -0.7) + rows(
        days, "B3", {"c": 0.0, "d": 0.0}, -0.7
    )
    m = pl.DataFrame(same).with_columns(pl.col("break_even_fee_bps").round(0))
    assert "by construction" in " ".join(m4.same_note(m, m))
    other = m.with_columns(
        pl.when(pl.col("label") == "B3").then(pl.col("break_even_fee_bps") + 0.1)
        .otherwise(pl.col("break_even_fee_bps")).alias("break_even_fee_bps")
    )  # fmt: skip
    assert m4.same_note(other, m) == []
