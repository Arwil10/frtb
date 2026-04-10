"""
sa/vega.py — SBM vega risk charge (d457 §96, §99, §105).

Sensitivity per option (§96):
    s_kl = vega_BS × σ_implied        (response to a relative shock in σ)

Earlier code had `vega × (1/S) × (1/σ)` which is not §96. Fixed here.
"""

from dataclasses import dataclass

from pricing.black_scholes import BSOption
from config import VEGA_RW, CORR_SCENARIOS
from sa._aggregation import bucket_charge, cross_bucket_charge


@dataclass
class VegaResult:
    charge_by_bucket: dict
    sensitivities:    list           # [(id, bucket, s_kl, ws_kl)]
    scenario_used:    str
    total:            float


# ---------------------------------------------------------------- §96 sens
def vega_sensitivity(opt: BSOption) -> float:
    """
    d457 §96: sensitivity to a relative shift in implied vol.
        s_kl = (vega_BS × σ) × n_units

    where n_units = notional_EUR / S is the number of underlying units
    implied by the EUR notional. vega_BS is per unit of underlying, so
    we scale by n_units to get the portfolio-level sensitivity in EUR.
    Signed by notional (long/short).
    """
    n_units = opt.notional / opt.S        # preserves sign
    return n_units * opt.vega() * opt.sigma


# ----------------------------------------------------------------- runner
def compute_vega_charge(options: list[BSOption]) -> VegaResult:
    if not options:
        return VegaResult({}, [], 'n/a', 0.0)

    sens_rows = []
    ws_by_bucket: dict[str, list[float]] = {}

    for opt in options:
        s  = vega_sensitivity(opt)
        rw = VEGA_RW.get(opt.bucket, VEGA_RW.get(opt.asset_class, 0.55))
        ws = s * rw
        sens_rows.append((opt.id, opt.bucket, s, ws))
        ws_by_bucket.setdefault(opt.bucket, []).append(ws)

    best_total, best_sc, best_k = -1.0, None, {}
    for name, corr in CORR_SCENARIOS.items():
        rho_same, rho_cross = corr['same_bucket'], corr['cross_bucket']
        k_by_bucket = {b: bucket_charge(ws, rho_same) for b, ws in ws_by_bucket.items()}
        s_by_bucket = {b: sum(ws) for b, ws in ws_by_bucket.items()}
        total = cross_bucket_charge(k_by_bucket, s_by_bucket, rho_cross)
        if total > best_total:
            best_total, best_sc, best_k = total, name, k_by_bucket

    return VegaResult(
        charge_by_bucket = best_k,
        sensitivities    = sens_rows,
        scenario_used    = best_sc or 'n/a',
        total            = best_total,
    )
