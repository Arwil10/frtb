"""
sa/engine.py — SA-TB runner: Delta + Vega + Curvature + DRC.

Capital_MR = Δ_charge + Vega_charge + Curvature_charge
RWA_total  = Capital_MR × 12.5 + RWA_DRC
"""

from dataclasses import dataclass

from config import CONVERSION_FACTOR
from portfolio.desks import Desk
from portfolio.drc   import get_desk_drc_positions
from sa.delta      import compute_delta_charge, DeltaResult
from sa.vega       import compute_vega_charge,  VegaResult
from sa.curvature  import compute_curvature_charge, CurvatureResult
from sa.drc import compute_drc, DRCResult


@dataclass
class SAResult:
    desk_id:             str
    delta:               DeltaResult
    vega:                VegaResult
    curvature:           CurvatureResult
    drc:                 DRCResult
    capital_mr:          float
    rwa_market:          float
    rwa_drc:             float
    rwa_total:           float

    # Compatibility shims for main.py print formatting
    @property
    def delta_charge(self)     -> float: return self.delta.total
    @property
    def vega_charge(self)      -> float: return self.vega.total
    @property
    def curvature_charge(self) -> float: return self.curvature.total
    @property
    def drc_rwa(self)          -> float: return self.rwa_drc


def run_sa(desk: Desk, verbose: bool = True) -> SAResult:
    delta_res     = compute_delta_charge(desk.positions, desk.options)
    vega_res      = compute_vega_charge(desk.options)
    curvature_res = compute_curvature_charge(desk.options)
    drc_res       = compute_drc(get_desk_drc_positions(desk.desk_id),
                                desk.desk_id, method='pd_based')

    capital_mr = delta_res.total + vega_res.total + curvature_res.total
    rwa_market = capital_mr * CONVERSION_FACTOR
    rwa_total  = rwa_market + drc_res.rwa_total

    result = SAResult(
        desk_id    = desk.desk_id,
        delta      = delta_res,
        vega       = vega_res,
        curvature  = curvature_res,
        drc        = drc_res,
        capital_mr = capital_mr,
        rwa_market = rwa_market,
        rwa_drc    = drc_res.rwa_total,
        rwa_total  = rwa_total,
    )

    if verbose:
        _print(result)
    return result


def _print(r: SAResult):
    print(f"\n{'=' * 65}")
    print(f"SA-TB — Desk: {r.desk_id}")
    print(f"{'=' * 65}")
    print(f"  Delta:     FX={r.delta.fx_charge:8.4f}  "
          f"Eq={r.delta.equity_charge:8.4f}  "
          f"total={r.delta.total:8.4f}  [{r.delta.scenario_used}]")
    print(f"  Vega:      {r.vega.total:8.4f}  [{r.vega.scenario_used}]")
    print(f"  Curvature: {r.curvature.total:8.4f}  [{r.curvature.scenario_used}]")
    print(f"  Capital MR:{r.capital_mr:8.4f}  ->  RWA MR = {r.rwa_market:8.4f}")
    print(f"  DRC:       {r.drc.drc_total:8.4f}  ->  RWA DRC = {r.rwa_drc:8.4f}")
    print(f"  {'-' * 50}")
    print(f"  RWA SA TOTAL: {r.rwa_total:.4f} mln EUR")
    print(f"{'=' * 65}")
