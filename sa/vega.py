"""
sa/vega.py — SBM vega risk charge
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
    n_units = opt.notional / opt.S        # MAR21.15: sensitivities expressed in reporting currency
    return n_units * opt.vega() * opt.sigma # MAR21.25: vega sensitivity = vega_BS × σ_implied

# TODO: Implement pair-wise maturity correlation decay per MAR21.93-21.94.
# ----------------------------------------------------------------- runner
def compute_vega_charge(options: list[BSOption]) -> VegaResult:
    if not options:
        return VegaResult({}, [], 'n/a', 0.0)

    sens_rows = []
    ws_by_bucket: dict[str, list[float]] = {}

    for opt in options:
        s  = vega_sensitivity(opt)                                           # MAR21.25: option-level vega sensitivity
        rw = VEGA_RW.get(opt.bucket, VEGA_RW.get(opt.asset_class, 0.55))   # MAR21.92, Table 13: vega risk weight per risk class
        ws = s * rw                                                          # MAR21.4(3): weighted sensitivity WS_k = s_k × RW_k
        sens_rows.append((opt.id, opt.bucket, s, ws))
        ws_by_bucket.setdefault(opt.bucket, []).append(ws)                  # MAR21.4(2): net sensitivity per risk factor

    best_total, best_sc, best_k = -1.0, None, {}
    for name, corr in CORR_SCENARIOS.items():                               # MAR21.6: three correlation scenarios (low/medium/high)
        rho_same, rho_cross = corr['same_bucket'], corr['cross_bucket']
        k_by_bucket = {b: bucket_charge(ws, rho_same)                      # MAR21.4(4): within-bucket aggregation using ρ_kl
                       for b, ws in ws_by_bucket.items()}
        s_by_bucket = {b: sum(ws) for b, ws in ws_by_bucket.items()}       # MAR21.4(5): S_b = sum of weighted sensitivities in bucket b
        total = cross_bucket_charge(k_by_bucket, s_by_bucket, rho_cross)   # MAR21.4(5): across-bucket aggregation using γ_bc
        if total > best_total:
            best_total, best_sc, best_k = total, name, k_by_bucket

    # MAR21.7(2): capital requirement = maximum across three correlation scenarios
    return VegaResult(
        charge_by_bucket = best_k,
        sensitivities    = sens_rows,
        scenario_used    = best_sc or 'n/a',
        total            = best_total,
    )
