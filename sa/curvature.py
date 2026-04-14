"""
sa/curvature.py — curvature risk charge (d457 §108, §121–122).

Per-option CVR for each shock direction (§108):
    CVR_k^up = -( V(S·(1+RW)) - V(S) - Δ·RW·S )  × notional_sign
    CVR_k^dn = -( V(S·(1-RW)) - V(S) + Δ·RW·S )  × notional_sign

Bucket aggregation (§121):
    K_b = sqrt( max(0, Σ max(CVR_k,0)² + Σ_{k≠l} ρ·CVR_k·CVR_l·ψ(CVR_k,CVR_l)) )
    with ψ = 0 if both CVR negative, else 1.

Cross-bucket (§122):
    K   = sqrt( Σ K_b² + Σ_{b≠c} γ²·S_b·S_c·ψ(S_b,S_c) )
Note: γ is SQUARED for curvature vs plain γ for delta/vega.
"""

from dataclasses import dataclass
import numpy as np

from pricing.black_scholes import BSOption
from config import CURVATURE_SHOCK, CORR_SCENARIOS


@dataclass
class CurvatureResult:
    cvr_by_option: list              # [(id, bucket, cvr_up, cvr_dn, cvr_worst)]
    k_by_bucket:   dict
    scenario_used: str
    total:         float


# ----------------------------------------------------------- per-option CVR
def _compute_cvr(opt: BSOption) -> tuple[float, float]:
    """
    BS price and delta are both expressed per unit of underlying. We scale
    by n_units = notional_EUR / S to convert to portfolio currency.
    """
    rw      = CURVATURE_SHOCK.get(opt.bucket, 0.15)  # MAR21.98: curvature RW = delta RW for FX and equity; MAR21.99: parallel shift for GIRR/CSR/commodity
    V0      = opt.price()                             # MAR21.5(2): current price V_i(x_k)
    delta   = opt.delta()                             # MAR21.5(2): delta sensitivity s_i^k; MAR21.5 FAQ1: same delta as used in delta risk capital requirement
    S       = opt.S
    n_units = opt.notional / S                        # MAR21.15: sensitivities expressed in reporting currency; signed by position direction

    V_up = opt.reprice(S_new=S * (1 + rw))            # MAR21.5(2): V_i(x_k^RW+) — price after upward shock
    V_dn = opt.reprice(S_new=S * (1 - rw))            # MAR21.5(2): V_i(x_k^RW-) — price after downward shock

    cvr_up = -n_units * ((V_up - V0) - delta *  rw * S)   # MAR21.5(2): CVR_k^up = -Σ_i [ V_i(x_k^RW+) - V_i(x_k) - RW_k * s_ik ]
    cvr_dn = -n_units * ((V_dn - V0) - delta * (-rw) * S) # MAR21.5(2): CVR_k^dn = -Σ_i [ V_i(x_k^RW-) - V_i(x_k) + RW_k * s_ik ]
    return cvr_up, cvr_dn


# ---------------------------------------------------- bucket / cross-bucket
def _psi(a: float, b: float) -> float:
    """MAR21.5(3): ψ = 0 if both CVR_k and CVR_l are negative, else 1."""
    return 0.0 if (a < 0 and b < 0) else 1.0


def _bucket_K(cvrs: list[float], rho: float) -> float:
    """MAR21.5(3): within-bucket aggregation of curvature risk positions."""
    n = len(cvrs)
    if n == 0:
        return 0.0
    pos_sq = sum(max(c, 0.0) ** 2 for c in cvrs)          # MAR21.5(3): Σ max(CVR_k, 0)²
    cross  = sum(
        rho * cvrs[i] * cvrs[j] * _psi(cvrs[i], cvrs[j]) # MAR21.5(3): ρ_kl^2 · CVR_k · CVR_l · ψ(CVR_k, CVR_l); MAR21.100: ρ_kl^2 = squared delta correlation
        for i in range(n) for j in range(n) if i != j
    )
    return float(np.sqrt(max(pos_sq + cross, 0.0)))        # MAR21.5(3): K_b = sqrt(max(0, ...))


def _cross_bucket_K(k_by_bucket: dict, s_by_bucket: dict, gamma: float) -> float:
    """MAR21.5(4): cross-bucket aggregation of curvature risk positions."""
    buckets = list(k_by_bucket.keys())
    n = len(buckets)
    if n == 0:
        return 0.0
    var = sum(k_by_bucket[b] ** 2 for b in buckets)        # MAR21.5(4): Σ K_b^2
    cov = sum(
        (gamma ** 2) * s_by_bucket[buckets[i]] * s_by_bucket[buckets[j]]
        * _psi(s_by_bucket[buckets[i]], s_by_bucket[buckets[j]])  # MAR21.5(4): ψ(S_b, S_c) — 0 if both S_b and S_c negative
        for i in range(n) for j in range(n) if i != j             # MAR21.101: γ_bc^2 — gamma is SQUARED for curvature
    )
    return float(np.sqrt(max(var + cov, 0.0)))


# ----------------------------------------------------------------- runner
def compute_curvature_charge(options: list[BSOption]) -> CurvatureResult:
    if not options:
        return CurvatureResult([], {}, 'n/a', 0.0)

    rows, cvrs_by_bucket = [], {}
    for opt in options:
        up, dn = _compute_cvr(opt)
        worst  = max(up, dn)                                # MAR21.5(3): K_b = max(K_b^up, K_b^dn) — select worst scenario per bucket
        rows.append((opt.id, opt.bucket, up, dn, worst))
        cvrs_by_bucket.setdefault(opt.bucket, []).append(worst)

    best_total, best_sc, best_k = -1.0, None, {}
    for name, corr in CORR_SCENARIOS.items():               # MAR21.6: three correlation scenarios (low/medium/high)
        rho_same, gamma = corr['same_bucket'], corr['cross_bucket']
        k_by_bucket = {b: _bucket_K(cvrs, rho_same)        # MAR21.5(3): within-bucket aggregation
                       for b, cvrs in cvrs_by_bucket.items()}
        s_by_bucket = {b: sum(cvrs)                         # MAR21.5(4): S_b = Σ CVR_k for bucket b (upward scenario selected)
                       for b, cvrs in cvrs_by_bucket.items()}
        total = _cross_bucket_K(k_by_bucket, s_by_bucket, gamma)  # MAR21.5(4): cross-bucket aggregation
        if total > best_total:
            best_total, best_sc, best_k = total, name, k_by_bucket

    # MAR21.7(2): capital requirement = maximum across three correlation scenarios
    return CurvatureResult(
        cvr_by_option = rows,
        k_by_bucket   = best_k,
        scenario_used = best_sc or 'n/a',
        total         = best_total,
    )
