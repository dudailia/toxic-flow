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


def toxic_episodes(toxic) -> int:
    """Number of maximal runs of consecutive steps marked toxic on the same side."""
    t = np.asarray(toxic)
    if not len(t):
        return 0
    starts = (t != 0) & np.concatenate([[True], t[1:] != t[:-1]])
    return int(starts.sum())


def quote_metrics(fills, steps) -> dict:
    """Diagnostics of how a strategy quotes (M4 diagnosis, exploratory; not section 6):
    cancels per quoting hour, median seconds from an order's request to its fill, share of
    steps with our target bid at or above the best bid (ask at or below the best ask), the
    median distance of each target from the mid in ticks, and the same by UTC hour."""
    hours = len(steps) * 0.1 / 3600 if len(steps) else float("nan")
    mid = (steps["best_bid_tick"] + steps["best_ask_tick"]) / 2
    bid_d, ask_d = mid - steps["bid_tick"], steps["ask_tick"] - mid
    with np.errstate(invalid="ignore"):
        bid_best = steps["bid_tick"] >= steps["best_bid_tick"]
        ask_best = steps["ask_tick"] <= steps["best_ask_tick"]
    wait = (fills["exch_ts"] - fills["local_ts"]) / 1e9

    def med(x):
        x = x[np.isfinite(x)]
        return float(np.median(x)) if len(x) else float("nan")

    hour = (steps["ts"] // 3_600_000_000_000) % 24
    fill_hour = (fills["exch_ts"] // 3_600_000_000_000) % 24
    hourly = [
        {"hour": int(h), "bid_dist_ticks": med(bid_d[hour == h]), "ask_dist_ticks": med(ask_d[hour == h]),
         "bid_at_best": float(bid_best[hour == h].mean()), "ask_at_best": float(ask_best[hour == h].mean()),
         "fills": int((fill_hour == h).sum())}
        for h in np.unique(hour)
    ]  # fmt: skip
    return {
        "cancels_per_hour": float(steps["cancels"].sum() / hours) if hours else float("nan"),
        "median_fill_wait_s": med(wait),
        "bid_at_best_share": float(bid_best.mean()) if len(steps) else float("nan"),
        "ask_at_best_share": float(ask_best.mean()) if len(steps) else float("nan"),
        "median_bid_dist_ticks": med(bid_d),
        "median_ask_dist_ticks": med(ask_d),
        # v2: share of quoting steps where the overlay marked a side toxic (section 4's p).
        "toxic_share": float((steps["toxic"] != 0).mean()) if len(steps) else float("nan"),
        # Runs of consecutive steps with the same toxic side: pulling a side costs its
        # queue place once per run, so two strategies with one share can differ here.
        "toxic_episodes": toxic_episodes(steps["toxic"]),
        "hourly_quotes": hourly,
    }


def no_print_share(fills, prints: dict, tick: float) -> float:
    """Share of our fills with no opposite print at or through our price at the fill's
    exchange time (PREREGISTRATION.md section 3, Q50). hftbacktest also fills a resting
    quote when the book moves through its price, with no trade there; a real venue may treat
    some of those fills differently, so the share is reported for each day.

    prints: aggressor side "b" or "s" -> (sorted exchange times, the price furthest through
    at each time: the highest buyer-initiated print, the lowest seller-initiated one). Our
    sell (side -1) is reached by a buyer-initiated print at or above its price, our buy by
    a seller-initiated print at or below it. Prices are compared in ticks, not as floats.
    """
    if not len(fills):
        return float("nan")
    printed = np.zeros(len(fills), bool)
    for side, agg, sign in ((-1, "b", 1), (1, "s", -1)):
        ts, px = prints[agg]
        mine = fills["side"] == side
        t = fills["exch_ts"][mine]
        if not len(ts) or not len(t):
            continue
        i = np.clip(np.searchsorted(ts, t), 0, len(ts) - 1)
        ours = np.round(fills["price"][mine] / tick)
        theirs = np.round(px[i] / tick)
        printed[mine] = (ts[i] == t) & (sign * (theirs - ours) >= 0)
    return float(1 - printed.mean())
