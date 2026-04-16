"""
ima/drcima.py — IMA Default Risk Charge (MAR33.18–33.37).

Vasicek one-factor Monte Carlo, 99.9% confidence, 1Y horizon (MAR33.20(5)).

Model:
    Z_s  ~ N(0,1)                     common systematic factor (MAR33.20(1))
    ε_is ~ N(0,1)                     idiosyncratic factor
    X_is = √ρ_i · Z_s + √(1-ρ_i) · ε_is
    default_is = 1[X_is < Φ⁻¹(PD_i)]
    loss_s = Σ_i default_is · JtD_net_i

DRC = max(0, percentile_99.9(losses))             (MAR33.22)

Known simplifications vs MAR33:
  - Single systematic factor instead of two types (regional + industry) (MAR33.20(1) FAQ3)
  - No 12-week average — single simulation used (MAR33.22)
  - Sovereign proxy PDs, not IRB-calibrated (MAR33.37)
  - N_SIM=100k; production requires 1M+ for tail stability (MAR33.34)
"""

from collections import defaultdict
from dataclasses import dataclass
import numpy as np
from scipy.stats import norm

from config import (
    DRC_CONFIDENCE, DRC_N_SIM, CONVERSION_FACTOR,
    IMA_DRC_PD_FLOOR,
    IMA_DRC_RHO_INTERNAL as IMA_DRC_RHO_SAME_BUCKET_SAME_SECTOR,
    EM_SECTORS,
)
from portfolio.drc import DRCPosition


# ============================================================================
# Result dataclasses
# ============================================================================
@dataclass
class ObligorMC:
    """Single obligor parameters used in Monte Carlo simulation."""
    obligor_id: str
    bucket:     str
    sector:     str
    pd:         float      # floored at IMA_DRC_PD_FLOOR per MAR33.24(2)
    threshold:  float      # Φ^-1(PD) — default threshold in standard normal space
    rho:        float      # systematic factor loading ρ (MAR33.20(1))
    jtd_net:    float      # net jump-to-default exposure (MAR33.25: netting per obligor)


@dataclass
class IMADRCResult:
    desk_id:       str
    n_simulations: int
    loss_mean:     float
    loss_std:      float
    loss_99_9:     float   # 99.9th percentile loss (MAR33.20(5))
    drc_total:     float   # max(loss_99_9, 0) (MAR33.22)
    rwa_total:     float   # drc_total × 12.5 (MAR33.46)
    obligors:      list[ObligorMC]


# ==================================
# Netting + obligor parameter build
# ==================================
def _build_obligors(positions: list[DRCPosition]) -> list[ObligorMC]:

    groups: dict[str, dict] = defaultdict(
        lambda: {'jtd_long': 0.0, 'jtd_short': 0.0,
                 'pd': 0.0, 'bucket': 'IG', 'sector': 'index'}
    )

    for p in positions:
        g = groups[p.obligor_id]
        g['pd']     = p.pd
        g['sector'] = p.sector
        g['bucket'] = 'EM' if p.sector in EM_SECTORS else p.rating_bucket  # MAR33.20(2): ρ per rating bucket
        jtd = p.jtd_gross
        if jtd >= 0:
            g['jtd_long']  += jtd   # MAR33.25
        else:
            g['jtd_short'] += abs(jtd)  # MAR33.25

    obligors = []
    for oid, g in groups.items():
        jtd_net = g['jtd_long'] - g['jtd_short']  # MAR33.25: net JtD per obligor
        if abs(jtd_net) < 1e-9:
            continue  # MAR33.25: fully offset positions excluded

        pd_floored = max(g['pd'], IMA_DRC_PD_FLOOR)  # MAR33.24(2): PD floor 0.03%

        rho = IMA_DRC_RHO_SAME_BUCKET_SAME_SECTOR.get(g['bucket'], 0.50)  # MAR33.27: correlation per bucket

        obligors.append(ObligorMC(
            obligor_id = oid,
            bucket     = g['bucket'],
            sector     = g['sector'],
            pd         = pd_floored,
            threshold  = float(norm.ppf(pd_floored)),  # MAR33.24(1): objective PD → normal threshold
            rho        = rho,
            jtd_net    = jtd_net,
        ))
    return obligors


# ============================================================================
# Vectorized Monte Carlo
# ============================================================================
def _simulate(obligors: list[ObligorMC], n_sim: int, seed: int = 42) -> np.ndarray:
    """
    MAR33.20(1): Vasicek one-factor model.
    MAR33.23: constant positions over 1Y horizon.
    MAR33.9: Monte Carlo simulation is an approved method.
    Shape: Z (n_sim,), eps (n_sim, n), X (n_sim, n), losses (n_sim,).
    """
    rng = np.random.default_rng(seed)
    n   = len(obligors)

    thresholds = np.array([o.threshold for o in obligors])  # (n,)
    rho        = np.array([o.rho       for o in obligors])  # (n,)
    jtd_net    = np.array([o.jtd_net   for o in obligors])  # (n,)

    sqrt_rho     = np.sqrt(rho)          # factor loading
    sqrt_one_rho = np.sqrt(1.0 - rho)   # idiosyncratic loading

    Z   = rng.standard_normal(n_sim)              # (n_sim,)   — systematic factor Z (MAR33.20(1))
    eps = rng.standard_normal((n_sim, n))          # (n_sim, n) — idiosyncratic factors
    X   = sqrt_rho * Z[:, None] + sqrt_one_rho * eps  # (n_sim, n) — asset returns

    defaults = (X < thresholds).astype(float)     # (n_sim, n) — 1 if default
    return defaults @ jtd_net                      # (n_sim,)   — portfolio loss per scenario


# ============================================================================
# Runner
# ============================================================================
def run_ima_drc(
    positions: list[DRCPosition],
    desk_id:   str,
    n_sim:     int  = DRC_N_SIM,   # MAR33.20(5): weekly VaR calc, 99.9%, 1Y
    seed:      int  = 42,
    verbose:   bool = True,
) -> IMADRCResult:

    if not positions:
        return _empty(desk_id, n_sim, verbose, reason='no positions')

    obligors = _build_obligors(positions)
    if not obligors:
        return _empty(desk_id, n_sim, verbose, reason='fully offset')  # MAR33.25

    losses = _simulate(obligors, n_sim, seed)

    loss_999 = float(np.quantile(losses, DRC_CONFIDENCE, method='higher'))

    # MAR33.22: DRC = max(single measure, 12-week avg)
    # Uproszczenie: używamy tylko pojedynczego pomiaru (brak 12-tygodniowej historii)
    drc = max(loss_999, 0.0)

    result = IMADRCResult(
        desk_id       = desk_id,
        n_simulations = n_sim,
        loss_mean     = float(np.mean(losses)),
        loss_std      = float(np.std(losses)),
        loss_99_9     = loss_999,
        drc_total     = drc,
        rwa_total     = drc * CONVERSION_FACTOR,  # MAR33.46: RWA = capital × 12.5
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


def _print(r: IMADRCResult) -> None:
    print(f"\n{'=' * 65}")
    print(f"IMA-DRC (Vasicek MC) — Desk: {r.desk_id}")
    print(f"{'=' * 65}")
    print(f"  Simulations: {r.n_simulations:,}   99.9% 1-tailed   1Y horizon")  # MAR33.20(5)
    print(f"  Obligors:")
    print(f"  {'Name':<18} {'Bucket':>6} {'PD (floored)':>13} {'ρ':>6} {'JtD_net':>10}")
    for ob in r.obligors:
        print(f"  {ob.obligor_id:<18} {ob.bucket:>6} {ob.pd:>13.3%} "  # MAR33.24(2): PD floor visible
              f"{ob.rho:>6.2f} {ob.jtd_net:>10.4f}")
    print(f"  Loss mean: {r.loss_mean:10.4f}   std: {r.loss_std:10.4f}")
    print(f"  VaR 99.9%: {r.loss_99_9:10.4f}   =>  IMA-DRC = {r.drc_total:.4f}")  # MAR33.22
    print(f"  RWA IMA-DRC: {r.rwa_total:.4f} mln EUR")                             # MAR33.46
    print(f"{'=' * 65}")
