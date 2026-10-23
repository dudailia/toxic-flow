"""Bivariate Hawkes process with an exponential kernel and one shared decay, fitted by
maximum likelihood (PREREGISTRATION.md section 5).

    lambda_k(t) = mu_k + sum_j alpha_kj * sum_{t_i of type j, t_i < t} exp(-beta (t - t_i))

Types: 0 = buyer-initiated (b), 1 = seller-initiated (s); alpha[k, j] is the effect of a
type-j event on the type-k intensity. Times are seconds from the start of a window [0, T].
Events at exactly the same instant do not excite one another (strict t_i < t), because
the model has no ties and collapsed market orders can still share a timestamp across
sides.
"""

import numpy as np
from numba import njit
from scipy.optimize import minimize

PARAMS = ("mu_b", "mu_s", "alpha_bb", "alpha_bs", "alpha_sb", "alpha_ss", "beta")


@njit(cache=True)
def loglik(times, types, T, mu, alpha, beta):
    """Log-likelihood in O(n) with the recursion R_j(t) = sum exp(-beta (t - t_i^j))."""
    r0, r1, last, ll = 0.0, 0.0, 0.0, 0.0
    n = len(times)
    i = 0
    while i < n:
        t = times[i]
        decay = np.exp(-beta * (t - last))
        r0 *= decay
        r1 *= decay
        last = t
        j = i
        while j < n and times[j] == t:  # every event at t sees the state from before t
            k = types[j]
            ll += np.log(mu[k] + alpha[k, 0] * r0 + alpha[k, 1] * r1)
            j += 1
        for m in range(i, j):
            if types[m] == 0:
                r0 += 1.0
            else:
                r1 += 1.0
        i = j
    comp = (mu[0] + mu[1]) * T
    for m in range(n):
        src = types[m]
        comp += (alpha[0, src] + alpha[1, src]) * (1.0 - np.exp(-beta * (T - times[m]))) / beta
    return ll - comp


def branching_ratio(alpha: np.ndarray, beta: float) -> float:
    """Spectral radius of alpha / beta: expected direct offspring per event. Below 1 means
    the process is stationary."""
    return float(max(abs(np.linalg.eigvals(alpha / beta))))


def _unpack(p: np.ndarray):
    return p[0:2], p[2:6].reshape(2, 2), p[6]


def _neg_ll(p: np.ndarray, days) -> float:
    mu, alpha, beta = _unpack(p)
    return -sum(loglik(t, k, T, mu, alpha, beta) for t, k, T in days)


def _hessian(f, p: np.ndarray, rel: float = 1e-4) -> np.ndarray:
    """Central-difference Hessian with steps relative to each parameter."""
    h = rel * np.abs(p)
    n = len(p)
    H = np.empty((n, n))
    for i in range(n):
        for j in range(i, n):

            def at(si, sj, i=i, j=j):
                q = p.copy()
                q[i] += si * h[i]
                q[j] += sj * h[j]
                return f(q)

            H[i, j] = H[j, i] = (at(1, 1) - at(1, -1) - at(-1, 1) + at(-1, -1)) / (4 * h[i] * h[j])
    return H


def fit(days: list[tuple[np.ndarray, np.ndarray, float]], beta0: float = 1.0) -> dict:
    """MLE pooled over days, each (times in seconds, types, T) an independent realisation.

    L-BFGS-B works on log-parameters so every parameter stays positive; standard errors
    come from the numerical Hessian of the negative log-likelihood in the natural
    parameters at the optimum.
    """
    days = [(np.asarray(t, np.float64), np.asarray(k, np.int64), float(T)) for t, k, T in days]
    total_t = sum(T for _, _, T in days)
    rates = [sum((k == j).sum() for _, k, _ in days) / total_t for j in (0, 1)]
    # Start: half of each rate from the baseline, excitation at 0.25 of beta0 everywhere.
    p0 = np.array([rates[0] / 2, rates[1] / 2, *(0.25 * beta0,) * 4, beta0])
    res = minimize(lambda x: _neg_ll(np.exp(x), days), np.log(p0), method="L-BFGS-B")
    p = np.exp(res.x)
    H = _hessian(lambda q: _neg_ll(q, days), p)
    try:
        se = np.sqrt(np.diag(np.linalg.inv(H)))
    except np.linalg.LinAlgError:
        se = np.full(len(p), np.nan)
    mu, alpha, beta = _unpack(p)
    return {
        "params": dict(zip(PARAMS, map(float, p), strict=True)),
        "se": dict(zip(PARAMS, map(float, se), strict=True)),
        "loglik": float(-res.fun),
        "n_events": int(sum(len(t) for t, _, _ in days)),
        "branching_ratio": branching_ratio(alpha, beta),
        "converged": bool(res.success),
        "message": str(res.message),
    }


@njit(cache=True)
def _own_compensators(times, types, mu, alpha, beta):
    """Lambda_k(t_i) = int_0^t_i lambda_k for k the type of event i, from strictly earlier
    events: mu_k t + sum_j alpha_kj (N_j - R_j) / beta, in O(n)."""
    n = len(times)
    out = np.empty(n)
    r = np.zeros(2)
    cnt = np.zeros(2)
    last = 0.0
    i = 0
    while i < n:
        t = times[i]
        decay = np.exp(-beta * (t - last))
        r[0] *= decay
        r[1] *= decay
        last = t
        j = i
        while j < n and times[j] == t:
            k = types[j]
            out[j] = (
                mu[k] * t + (alpha[k, 0] * (cnt[0] - r[0]) + alpha[k, 1] * (cnt[1] - r[1])) / beta
            )
            j += 1
        for m in range(i, j):
            r[types[m]] += 1.0
            cnt[types[m]] += 1.0
        i = j
    return out


def rescaled_residuals(times, types, mu, alpha, beta) -> dict[int, np.ndarray]:
    """Per type, the compensator increments between its own events (time-rescaling). Under
    the fitted model they are i.i.d. Exp(1)."""
    lam = _own_compensators(
        np.asarray(times, np.float64), np.asarray(types, np.int64), np.asarray(mu, np.float64),
        np.asarray(alpha, np.float64), float(beta),
    )  # fmt: skip
    return {k: np.diff(np.concatenate([[0.0], lam[np.asarray(types) == k]])) for k in (0, 1)}


def residual_report(times, types, mu, alpha, beta) -> dict:
    """Mean and the KS test against Exp(1) of each type's residuals (SPEC.md AC3.5)."""
    from scipy import stats

    res = rescaled_residuals(times, types, mu, alpha, beta)
    out = {}
    for k, name in ((0, "b"), (1, "s")):
        ks = stats.kstest(res[k], "expon")
        out[name] = {
            "n": int(len(res[k])),
            "mean": float(res[k].mean()),
            "ks_statistic": float(ks.statistic),
            "ks_pvalue": float(ks.pvalue),
        }
    return out
