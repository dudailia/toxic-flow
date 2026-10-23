"""Day metrics for one strategy in one cell (PREREGISTRATION.md section 6).

Gross PnL G = change in cash + inventory times the mark mid, fees excluded; traded notional
N = sum |qty * price|; break-even maker fee BEF = 10,000 G / N in bp; net PnL at fee f is
G - f N / 10,000. Inventory variance is over q sampled each second, in order sizes. Fill
rate is fills per quoting hour; quote presence is the share of decision steps with an
order of ours on both sides.
"""

import numpy as np

SAMPLE_EVERY_STEPS = 10  # 100 ms steps, so once a second


def inventory_at(steps: np.ndarray, times_ns) -> list:
    """Position at the first decision step at or after each time, or None if past the end."""
    out = []
    for t in times_ns:
        i = int(np.searchsorted(steps["ts"], t, side="left"))
        out.append(float(steps["position"][i]) if i < len(steps) else None)
    return out


def day_metrics(fills, steps, mark_mid, order_qty, fee_levels_bps, funding_ns=()) -> dict:
    signed = fills["side"] * fills["qty"]
    position = float(signed.sum())
    gross = float(-(signed * fills["price"]).sum() + position * mark_mid)
    notional = float((fills["qty"] * fills["price"]).sum())
    step_s = float(np.median(np.diff(steps["ts"]))) / 1e9 if len(steps) > 1 else 0.1
    hours = len(steps) * step_s / 3600
    q = steps["position"][::SAMPLE_EVERY_STEPS] / order_qty
    return {
        "fills": int(len(fills)),
        "gross_pnl": gross,
        "traded_notional": notional,
        "break_even_fee_bps": 1e4 * gross / notional if notional else float("nan"),
        "net_pnl": {name: gross - f * notional / 1e4 for name, f in fee_levels_bps.items()},
        "end_position": position,
        "inventory_variance": float(q.var()),
        "fill_rate_per_hour": len(fills) / hours if hours else float("nan"),
        "quote_presence": float(steps["both_quoted"].mean()),
        "inventory_at_funding": inventory_at(steps, funding_ns),
    }
