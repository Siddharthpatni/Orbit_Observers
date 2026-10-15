"""Statistical tools for Monte Carlo outcomes (Handbook Sections 10-11).

Pure functions with no plotting or file I/O. Methods:

* Wilson score interval for a proportion (pass/abort/unsafe rates). Unlike the
  textbook ``p +/- 1.96*SE`` it stays inside [0, 1] and is honest near 0 or 1.
* Normal-approximation interval for a mean (delta-v, time, error).
* Paired comparison of two tiers on the *same* seeds: exact McNemar test plus
  the Agresti-Min adjusted interval for the difference in pass rates.
* Sample-size planning and running (convergence) estimates.
"""
import math
from typing import Dict, Sequence, Tuple
import numpy as np

Z95 = 1.959963984540054


def wilson_interval(k_success: int, n_total: int, z: float = Z95) -> Tuple[float, float, float]:
    """Return (p_hat, low, high) for k successes in n trials."""
    if n_total <= 0:
        return float("nan"), 0.0, 1.0
    if not 0 <= k_success <= n_total:
        raise ValueError("k_success must lie in [0, n_total]")
    p_hat = k_success / n_total
    z2 = z * z
    denom = 1.0 + z2 / n_total
    center = (p_hat + z2 / (2.0 * n_total)) / denom
    half_width = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n_total + z2 / (4.0 * n_total ** 2))
    # Clamp so rounding can never put the estimate outside its own interval (k = 0 or k = n).
    return p_hat, max(0.0, min(p_hat, center - half_width)), min(1.0, max(p_hat, center + half_width))


def wilson_ci_95(k_success: int, n_total: int, z: float = Z95) -> Tuple[float, float, float]:
    """Backward-compatible alias of ``wilson_interval`` (returns 0s when n = 0)."""
    if n_total <= 0:
        return 0.0, 0.0, 0.0
    return wilson_interval(k_success, n_total, z)


def mean_interval(values: Sequence[float], z: float = Z95) -> Tuple[float, float, float]:
    """Return (mean, low, high); NaNs are ignored. Normal approximation, fine for n >= ~30."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(arr.mean())
    if arr.size < 2:
        return mean, float("nan"), float("nan")
    half = z * float(arr.std(ddof=1)) / math.sqrt(arr.size)
    return mean, mean - half, mean + half


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant-pair counts.

    b = pairs where only A passed, c = pairs where only B passed. Concordant
    pairs carry no information about which option is better.
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, (2 * tail) / 2 ** n)  # exact integer ratio: no float overflow for large n


def paired_difference(pass_a: Sequence[bool], pass_b: Sequence[bool], z: float = Z95) -> Dict[str, float]:
    """Compare pass rates of B versus A evaluated on the same seeds.

    Returns the difference p_B - p_A with an Agresti-Min (2005) adjusted Wald
    interval (add 0.5 to each cell of the 2x2 table), the discordant counts and
    the exact McNemar p-value.
    """
    a = np.asarray(pass_a, dtype=bool)
    b_arr = np.asarray(pass_b, dtype=bool)
    if a.shape != b_arr.shape:
        raise ValueError("paired samples must have the same length")
    n = int(a.size)
    only_a = int(np.sum(a & ~b_arr))
    only_b = int(np.sum(~a & b_arr))
    if n == 0:
        return {"n_pairs": 0, "p_a": float("nan"), "p_b": float("nan"), "diff": float("nan"),
                "diff_ci95_low": float("nan"), "diff_ci95_high": float("nan"),
                "only_a_pass": 0, "only_b_pass": 0, "mcnemar_p": 1.0}
    n_adj = n + 2.0
    p12, p21 = (only_a + 0.5) / n_adj, (only_b + 0.5) / n_adj
    diff_adj = p21 - p12
    se = math.sqrt(max(0.0, (p12 + p21) - diff_adj ** 2) / n_adj)
    return {
        "n_pairs": n,
        "p_a": float(a.mean()),
        "p_b": float(b_arr.mean()),
        "diff": (only_b - only_a) / n,
        "diff_ci95_low": max(-1.0, diff_adj - z * se),
        "diff_ci95_high": min(1.0, diff_adj + z * se),
        "only_a_pass": only_a,
        "only_b_pass": only_b,
        "mcnemar_p": mcnemar_exact_p(only_a, only_b),
    }


def runs_for_half_width(p: float, half_width: float, z: float = Z95) -> int:
    """Runs needed so a proportion near ``p`` has a 95% interval of +/- ``half_width``."""
    if not 0 < half_width < 1:
        raise ValueError("half_width must be in (0, 1)")
    p = min(max(p, 0.0), 1.0)
    return int(math.ceil(z * z * max(p * (1.0 - p), 1e-12) / half_width ** 2))


def zero_event_upper_bound(n_total: int, confidence: float = 0.95) -> float:
    """Exact one-sided upper bound on a probability when 0 events occur in n runs.

    For 95% this is about 3/n (the "rule of three"). It bounds the rate *within
    the model*; it says nothing about failure physics the model omits.
    """
    if n_total <= 0:
        return 1.0
    return 1.0 - (1.0 - confidence) ** (1.0 / n_total)


def running_proportion(successes: Sequence[bool], z: float = Z95) -> np.ndarray:
    """Running estimate and Wilson band after 1..n runs: array of shape (n, 3)."""
    s = np.asarray(successes, dtype=bool)
    k = np.cumsum(s)
    return np.array([wilson_interval(int(k[i]), i + 1, z) for i in range(s.size)], dtype=float).reshape(-1, 3)
