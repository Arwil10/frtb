"""
ima/drcima.py — IMA Default Risk Charge (d457 §186–191).

Vasicek one-factor Monte Carlo, 99.9% confidence, 1Y horizon.

For each simulation s:
    Z_s  ~ N(0, 1)                    common market factor
    ε_is ~ N(0, 1)                    idiosyncratic
    X_is = √ρ_i · Z_s + √(1-ρ_i) · ε_is
    default_is = 1[X_is < Φ⁻¹(PD_i)]
    loss_s = Σ_i default_is · JtD_net_i

IMA-DRC = max(0, percentile_99.9(losses)).
"""

from collections import defaultdict
from dataclasses import dataclass
import numpy as np
from scipy.stats import norm

from config import (
    DRC_CONFIDENCE, DRC_N_SIM, CONVERSION_FACTOR,
    IMA_DRC_RHO_INTERNAL as IMA_DRC_RHO_SAME_BUCKET_SAME_SECTOR, EM_SECTORS,
)
from portfolio.drc import DRCPosition


# ============================================================================
# Result dataclasses
# ============================================================================
@dataclass
class ObligorMC:
    obligor_id: str
    bucket:     str
    sector:     str
    pd:         float
    threshold:  float
    rho:        float                 # pair-wise same-bucket ρ (diagonal)
    jtd_net:    float


@dataclass
class IMADRCResult:
    desk_id:       str
    n_simulations: int
    loss_mean:     float
    loss_std:      float
    loss_99_9:     float
    drc_total:     float
    rwa_total:     float
    obligors:      list[ObligorMC]


# ============================================================================
# Netting + obligor parameter build
# ============================================================================
def _build_obligors(positions: list[DRCPosition]) -> list[ObligorMC]:
    groups: dict[str, dict] = defaultdict(
        lambda: {'jtd_long': 0.0, 'jtd_short': 0.0,
                 'pd': 0.0, 'bucket': 'IG', 'sector': 'index'}
    )
    for p in positions:
        g = groups[p.obligor_id]
        g['pd']     = p.pd
        g['sector'] = p.sector
        g['bucket'] = 'EM' if p.sector in EM_SECTORS else p.rating_bucket
        jtd = p.jtd_gross
        if jtd >= 0:
            g['jtd_long']  += jtd
        else:
            g['jtd_short'] += abs(jtd)

    obligors = []
    for oid, g in groups.items():
        jtd_net = g['jtd_long'] - g['jtd_short']
        if abs(jtd_net) < 1e-9:
            continue
        rho = IMA_DRC_RHO_SAME_BUCKET_SAME_SECTOR.get(g['bucket'], 0.50)
        obligors.append(ObligorMC(
            obligor_id = oid,
            bucket     = g['bucket'],
            sector     = g['sector'],
            pd         = g['pd'],
            threshold  = float(norm.ppf(g['pd'])),
            rho        = rho,
            jtd_net    = jtd_net,
        ))
    return obligors


# ============================================================================
# Vectorized Monte Carlo
# ============================================================================
def _simulate(obligors: list[ObligorMC], n_sim: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n   = len(obligors)

    thresholds = np.array([o.threshold for o in obligors])
    rho        = np.array([o.rho       for o in obligors])
    jtd_net    = np.array([o.jtd_net   for o in obligors])

    sqrt_rho     = np.sqrt(rho)
    sqrt_one_rho = np.sqrt(1.0 - rho)

    Z   = rng.standard_normal(n_sim)                     # (n_sim,)
    eps = rng.standard_normal((n_sim, n))                # (n_sim, n)
    X   = sqrt_rho * Z[:, None] + sqrt_one_rho * eps     # (n_sim, n)

    defaults = (X < thresholds).astype(float)
    return defaults @ jtd_net                            # (n_sim,)


# ============================================================================
# Runner
# ============================================================================
def run_ima_drc(
    positions: list[DRCPosition],
    desk_id:   str,
    n_sim:     int  = DRC_N_SIM,
    seed:      int  = 42,
    verbose:   bool = True,
) -> IMADRCResult:

    if not positions:
        return _empty(desk_id, n_sim, verbose, reason='no positions')

    obligors = _build_obligors(positions)
    if not obligors:
        return _empty(desk_id, n_sim, verbose, reason='fully offset')

    losses   = _simulate(obligors, n_sim, seed)
    # Use 'higher' interpolation — at 99.9% with 10k samples we want the
    # conservative side of the tail, not an interpolated average.
    loss_999 = float(np.percentile(losses, DRC_CONFIDENCE * 100, method='higher'))
    drc      = max(loss_999, 0.0)

    result = IMADRCResult(
        desk_id       = desk_id,
        n_simulations = n_sim,
        loss_mean     = float(np.mean(losses)),
        loss_std      = float(np.std(losses)),
        loss_99_9     = loss_999,
        drc_total     = drc,
        rwa_total     = drc * CONVERSION_FACTOR,
        obligors      = obligors,
    )
    if verbose:
        _print(result)
    return result


def _empty(desk_id: str, n_sim: int, verbose: bool, reason: str) -> IMADRCResult:
    r = IMADRCResult(desk_id, n_sim, 0.0, 0.0, 0.0, 0.0, 0.0, [])
    if verbose:
        print(f"\nIMA-DRC [{desk_id}]: {reason} -> 0.00 mln EUR")
    return r


def _print(r: IMADRCResult):
    print(f"\n{'=' * 65}")
    print(f"IMA-DRC (Vasicek MC) — Desk: {r.desk_id}")
    print(f"{'=' * 65}")
    print(f"  Simulations: {r.n_simulations:,}   99.9%   1Y horizon")
    print(f"  Obligors:")
    print(f"  {'Name':<18} {'Bucket':>6} {'PD':>8} {'ρ':>6} {'JtD_net':>10}")
    for ob in r.obligors:
        print(f"  {ob.obligor_id:<18} {ob.bucket:>6} {ob.pd:>8.3%} "
              f"{ob.rho:>6.2f} {ob.jtd_net:>10.4f}")
    print(f"  Loss mean: {r.loss_mean:10.4f}   std: {r.loss_std:10.4f}")
    print(f"  VaR 99.9%: {r.loss_99_9:10.4f}   =>  IMA-DRC = {r.drc_total:.4f}")
    print(f"  RWA IMA-DRC: {r.rwa_total:.4f} mln EUR")
    print(f"{'=' * 65}")
