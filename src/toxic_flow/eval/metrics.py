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


def window_metrics(fills, steps, mark_mid, from_ns: int) -> dict:
    """Gross PnL, notional, fills and BEF from from_ns to the end of the day, for scoring
    candidates that start quoting at different times over one window (Q45, section 4).

    A fill belongs to the window when its exchange time is at or after from_ns. Inventory
    held at from_ns enters at the mid of the first step at or after from_ns, so the window's
    gross PnL is the day's equity at the end minus the equity at from_ns:
    G_w = -sum_window(side qty price) + q_end mark - q_from mid_from.
    """
    inside = fills["exch_ts"] >= from_ns
    signed = fills["side"] * fills["qty"]
    i = int(np.searchsorted(steps["ts"], from_ns, side="left"))
    mids = steps["mid"][i:]
    finite = np.flatnonzero(np.isfinite(mids))
    q_from = float(signed[~inside].sum())
    if q_from != 0.0 and not len(finite):
        raise ValueError("inventory at the window start but no mid after it")
    mid_from = float(mids[finite[0]]) if len(finite) else 0.0
    gross = float(
        -(signed[inside] * fills["price"][inside]).sum()
        + signed.sum() * mark_mid
        - q_from * mid_from
    )
    notional = float((fills["qty"][inside] * fills["price"][inside]).sum())
    return {
        "fills": int(inside.sum()),
        "gross_pnl": gross,
        "traded_notional": notional,
        "break_even_fee_bps": 1e4 * gross / notional if notional else float("nan"),
    }
