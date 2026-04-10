"""
sa/_aggregation.py — SBM aggregation primitives (d457 §54).

Formula appears in delta, vega and curvature — extracted to avoid duplication.
"""

import numpy as np


def bucket_charge(weighted: list[float], rho: float) -> float:
    """
    K_b = sqrt( max(0,  Σ WS_i² + Σ_{i≠j} ρ·WS_i·WS_j) )
        = sqrt( max(0,  (1-ρ)·Σ WS_i² + ρ·(Σ WS_i)² ) )
    """
    if not weighted:
        return 0.0
    ws = np.asarray(weighted, dtype=float)
    var = float((ws ** 2).sum() + rho * (ws.sum() ** 2 - (ws ** 2).sum()))
    return float(np.sqrt(max(var, 0.0)))


def cross_bucket_charge(k_by_bucket: dict, s_by_bucket: dict, gamma: float) -> float:
    """
    Cross-bucket aggregation (d457 §54).

    K = sqrt( max(0, Σ K_b² + Σ_{b≠c} γ·S_b·S_c) )

    where S_b = Σ WS_i clipped to [-K_b, K_b] (the "alternative" treatment
    is not used here; we use plain S_b = sum of weighted sensitivities).
    """
    buckets = list(k_by_bucket.keys())
    if not buckets:
        return 0.0
    k = np.asarray([k_by_bucket[b] for b in buckets], dtype=float)
    s = np.asarray([s_by_bucket[b] for b in buckets], dtype=float)
    var = float((k ** 2).sum() + gamma * (s.sum() ** 2 - (s ** 2).sum()))
    return float(np.sqrt(max(var, 0.0)))
