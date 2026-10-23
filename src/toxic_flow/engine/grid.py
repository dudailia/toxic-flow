"""Expand a run config over the queue-model and latency grid (SPEC.md M2).

Queue models: risk-averse, power n = 3, power n = 2, log (docs/ENGINE.md, Queue models;
the variant choice is open question Q2). Latency: low (order latency = feed latency),
high (3x), and zero only when a config asks for it (canary C3).
"""

import hashlib
import json

QUEUE_MODELS = {
    "risk_averse": ("risk_adverse_queue_model", ()),
    "power3": ("power_prob_queue_model", (3.0,)),
    "power2": ("power_prob_queue_model", (2.0,)),
    "log": ("log_prob_queue_model", ()),
}
LATENCY_MUL = {"low": 1.0, "high": 3.0, "zero": 0.0}


def config_hash(cfg: dict) -> str:
    """First 12 hex digits of the SHA-256 of the config as canonical JSON."""
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def expand(cfg: dict) -> list[dict]:
    """One cell per day, strategy, queue model and latency setting."""
    return [
        {"day": str(day), "strategy": s, "queue": q, "latency": lat}
        for day in cfg["days"]
        for s in cfg["strategies"]
        for q in cfg["queue_models"]
        for lat in cfg["latencies"]
    ]
