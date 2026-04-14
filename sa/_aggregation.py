"""
sa/_aggregation.py — SBM aggregation primitives (d457 §54).

Formula appears in delta, vega and curvature — extracted to avoid duplication.
"""

import numpy as np


def bucket_charge(weighted: list[float], rho: float) -> float:

    if not weighted:
        return 0.0
    ws = np.asarray(weighted, dtype=float)
    var = float((ws ** 2).sum() + rho * (ws.sum() ** 2 - (ws ** 2).sum()))
    return float(np.sqrt(max(var, 0.0)))


def cross_bucket_charge(k_by_bucket: dict, s_by_bucket: dict, gamma: float) -> float:

    buckets = list(k_by_bucket.keys())
    if not buckets:
        return 0.0
    k = np.asarray([k_by_bucket[b] for b in buckets], dtype=float)
    s = np.asarray([s_by_bucket[b] for b in buckets], dtype=float)
    var = float((k ** 2).sum() + gamma * (s.sum() ** 2 - (s ** 2).sum()))
    return float(np.sqrt(max(var, 0.0)))
