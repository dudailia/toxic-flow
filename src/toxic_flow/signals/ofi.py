"""B2 signal: best-level order-flow imbalance (Cont, Kukanov and Stoikov 2014;
PREREGISTRATION.md section 5).

Between consecutive best-bid-and-offer states n - 1 and n:

    e_n = 1{Pb_n >= Pb_n-1} qb_n - 1{Pb_n <= Pb_n-1} qb_n-1
        - 1{Pa_n <= Pa_n-1} qa_n + 1{Pa_n >= Pa_n-1} qa_n-1

OFI_W(t) sums e_n over updates with local_ts in (t - W, t]; u = tanh(OFI_W / s_W) with
s_W the trailing standard deviation of OFI_W over the last norm_steps decision steps
(30 minutes of 100 ms steps by default), and a = |OFI_W|. Every quantity at t uses only
updates received by t.
"""

import numpy as np

NORM_STEPS = 18_000  # 30 minutes of 100 ms decision steps


def ofi_contributions(bbo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(local_ts of each update after the first, e_n) from rows of data.book.BBO_DTYPE."""
    # Prices come from the engine as tick * tick_size; round so equal prices compare equal.
    pb, pa = np.round(bbo["bid_px"], 9), np.round(bbo["ask_px"], 9)
    qb, qa = bbo["bid_qty"], bbo["ask_qty"]
    e = (
        (pb[1:] >= pb[:-1]) * qb[1:]
        - (pb[1:] <= pb[:-1]) * qb[:-1]
        - (pa[1:] <= pa[:-1]) * qa[1:]
        + (pa[1:] >= pa[:-1]) * qa[:-1]
    )
    return bbo["local_ts"][1:], e


def ofi_window(update_ts: np.ndarray, e: np.ndarray, decision_ts: np.ndarray, window_s: float):
    """OFI_W at each decision time: the sum of e_n with update time in (t - W, t]."""
    cum = np.concatenate([[0.0], np.cumsum(e)])
    hi = np.searchsorted(update_ts, decision_ts, side="right")
    lo = np.searchsorted(update_ts, decision_ts - int(window_s * 1e9), side="right")
    return cum[hi] - cum[lo]


def trailing_std(x: np.ndarray, n: int) -> np.ndarray:
    """Population standard deviation of the last n values up to and including each one;
    NaN until n values exist."""
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x * x)])
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        s1 = c1[n:] - c1[:-n]
        s2 = c2[n:] - c2[:-n]
        out[n - 1 :] = np.sqrt(np.maximum(s2 / n - (s1 / n) ** 2, 0.0))
    return out


def ofi_signal(bbo: np.ndarray, decision_ts: np.ndarray, window_s: float, norm_steps=NORM_STEPS):
    """(u, a, OFI_W) at each decision time. u is 0 until the normaliser has norm_steps
    values or while it is 0."""
    ts, e = ofi_contributions(bbo)
    ofi = ofi_window(ts, e, decision_ts, window_s)
    s = trailing_std(ofi, norm_steps)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = np.where(s > 0, np.tanh(ofi / s), 0.0)
    return u, np.abs(ofi), ofi
