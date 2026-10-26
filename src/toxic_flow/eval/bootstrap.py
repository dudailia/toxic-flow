"""Confirmatory analysis (PREREGISTRATION.md sections 8, 9 and 11).

D_i = BEF_B3,i - BEF_B2b,i per test day in the primary cell. The paired day-level bootstrap
(10,000 resamples, seed 1729) gives a 95% percentile interval; the paired t interval is the
sensitivity check. If the two disagree on whether 0 is inside, the result is inconclusive.
H1 holds only if both exclude 0 and the point estimate has the same sign in all 8 cells.
"""

import numpy as np
from scipy import stats

SEED = 1729
N_RESAMPLES = 10_000

# Section 11, verbatim apart from the numbers, which are filled from results.
STATEMENTS = {
    "holds_positive": "The fitted Hawkes overlay added {mean} bp of edge per unit of notional over a "
    "decay-weighted trade count, with interval [{lo}, {hi}], in every queue and latency cell.",
    "no_detectable_difference": "No detectable difference between the Hawkes overlay and a "
    "decay-weighted trade count. The study could detect effects of {mde} bp or larger.",
    "inconclusive": "Inconclusive: the point estimate is large but the test set is too small to "
    "separate it from noise.",
    "does_not_hold": "Does not hold. The result depends on the queue or latency model.",
    "holds_negative": "The Hawkes overlay did worse than a decay-weighted trade count by {mean} bp, "
    "interval [{lo}, {hi}].",
}
# Not section 11 outcomes. With fewer than two paired days there is no interval to judge.
# When the intervals disagree about 0 but |mean| < MDE, section 8 says "inconclusive" and
# section 11's sentence ("the point estimate is large") would be false (Q36).
NOT_COMPUTED = "No conclusion: fewer than two paired days, so there is no interval."
STATEMENTS["intervals_disagree"] = (
    "Inconclusive: the bootstrap and t intervals disagree on whether 0 is inside, and the "
    "point estimate, {mean} bp, is below the minimum detectable effect of {mde} bp."
)


def paired_differences(a: dict, b: dict) -> tuple[list[str], np.ndarray, list[str]]:
    """a and b map day -> (BEF, fills). A day where either has zero fills is dropped from
    the pair and reported (section 8). Returns (days, D = a - b, dropped days)."""
    days, d, dropped = [], [], []
    for day in sorted(set(a) & set(b)):
        if a[day][1] == 0 or b[day][1] == 0:
            dropped.append(day)
        else:
            days.append(day)
            d.append(a[day][0] - b[day][0])
    return days, np.array(d), dropped


def bootstrap_ci(d: np.ndarray, n: int = N_RESAMPLES, seed: int = SEED, level: float = 0.95):
    """Percentile interval for the mean of d from n resamples of days with replacement."""
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    tail = round(50 * (1 - level), 10)  # 2.5 exactly, not 2.5000000000000027
    lo, hi = np.percentile(d[idx].mean(axis=1), [tail, 100 - tail])
    return float(lo), float(hi)


def t_interval(d: np.ndarray, level: float = 0.95):
    half = stats.t.ppf(0.5 + level / 2, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
    return float(d.mean() - half), float(d.mean() + half)


def mde(s: float, n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """(z_{1 - alpha/2} + z_power) * s / sqrt(n): 2.80 s / 4 = 0.70 s for n = 16 (section 9)."""
    return float((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * s / np.sqrt(n))


def conclusion(boot_ci, t_ci, mean: float, cell_signs, mde_bp: float) -> dict:
    """The pre-committed statement (section 11) for a primary result.

    cell_signs: the sign of the point estimate in each of the 8 queue and latency cells.
    """
    if not np.all(np.isfinite([*boot_ci, *t_ci, mean])):
        return {"key": "not_computed", "statement": NOT_COMPUTED}  # NaN would read as "excludes 0"
    excludes = [not (lo <= 0 <= hi) for lo, hi in (boot_ci, t_ci)]
    if excludes[0] != excludes[1]:
        # Section 8: the two intervals disagree about 0.
        key = "inconclusive" if abs(mean) >= mde_bp else "intervals_disagree"
    elif excludes[0]:
        same = all(np.sign(s) == np.sign(mean) for s in cell_signs)
        key = ("holds_positive" if mean > 0 else "holds_negative") if same else "does_not_hold"
    else:
        key = "no_detectable_difference" if abs(mean) < mde_bp else "inconclusive"
    lo, hi = boot_ci
    text = STATEMENTS[key].format(
        # Four decimals: the MDE is a few hundredths of a bp, which two would round away.
        mean=f"{abs(mean):.4f}", lo=f"{lo:.4f}", hi=f"{hi:.4f}", mde=f"{mde_bp:.4f}"
    )
    return {"key": key, "statement": text}


def selectivity(notional_b3, notional_b2b) -> dict:
    """Section 8 selectivity check: the median over test days of B3 / B2b traded notional.
    Below 0.5, any effect is labelled selectivity rather than better pricing."""
    ratio = float(np.median(np.asarray(notional_b3) / np.asarray(notional_b2b)))
    return {"median_notional_ratio": ratio, "flag": ratio < 0.5}
