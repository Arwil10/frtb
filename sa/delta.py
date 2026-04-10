"""
sa/delta.py — SBM delta risk charge (d457 §55, §58–60).

FX: §55 — single cross-pair correlation ρ = 0.60.
Equity: §55 tables 7–8 — bucket-level aggregation with per-scenario ρ / γ.

Options contribute their delta-equivalent exposure:
    delta_eq_EUR = (notional_EUR / S) × Δ_BS × S = notional × Δ_BS
which is then treated as a linear position in the same bucket.
"""

from dataclasses import dataclass
import pandas as pd

from config import FX_DELTA_RW, FX_CORR, EQUITY_DELTA_RW, CORR_SCENARIOS
from pricing.black_scholes import BSOption
from sa._aggregation import bucket_charge, cross_bucket_charge


@dataclass
class DeltaResult:
    fx_charge:      float
    equity_charge:  float
    scenario_used:  str
    total:          float


# ----------------------------------------------------------- option -> delta
def _option_delta_equivalents(options: list[BSOption]) -> list[dict]:
    """
    Convert each option to a synthetic linear position with:
      exposure_EUR = notional × Δ_BS
      asset_class, bucket inherited from option.
    """
    rows = []
    for o in options:
        rows.append({
            'Asset_Class':  o.asset_class,
            'Bucket':       o.bucket,
            'Exposure_EUR': o.notional * o.delta(),
            'ID':           o.id,
            'Ticker':       o.underlying,
        })
    return rows


# --------------------------------------------------------------------- FX
def _fx_delta(df: pd.DataFrame) -> float:
    """FX delta: WS_k = RW × exposure_k, aggregated with ρ = 0.60 (§55)."""
    if df.empty:
        return 0.0
    ws = (df['Exposure_EUR'] * FX_DELTA_RW).tolist()
    return bucket_charge(ws, FX_CORR)


# ----------------------------------------------------------------- equity
def _equity_delta(df: pd.DataFrame, rho_same: float, rho_cross: float) -> float:
    """Equity delta: bucket-level SBM then cross-bucket with γ = rho_cross."""
    if df.empty:
        return 0.0
    k_by_bucket: dict[str, float] = {}
    s_by_bucket: dict[str, float] = {}
    for bucket, group in df.groupby('Bucket'):
        rw = EQUITY_DELTA_RW.get(bucket, 0.55)
        ws = (group['Exposure_EUR'] * rw).tolist()
        k_by_bucket[bucket] = bucket_charge(ws, rho_same)
        s_by_bucket[bucket] = float(sum(ws))
    return cross_bucket_charge(k_by_bucket, s_by_bucket, rho_cross)


# ----------------------------------------------------------------- runner
def compute_delta_charge(
    linear_df: pd.DataFrame,
    options:   list[BSOption] | None = None,
) -> DeltaResult:
    """
    Combine linear positions and option delta-equivalents, then pick the
    max over the three correlation scenarios (d457 §54).
    """
    # Merge linear + option-delta-equivalents in a single DataFrame
    frames = [linear_df[['Asset_Class', 'Bucket', 'Exposure_EUR']]]
    if options:
        frames.append(pd.DataFrame(_option_delta_equivalents(options))
                      [['Asset_Class', 'Bucket', 'Exposure_EUR']])
    df = pd.concat(frames, ignore_index=True)

    df_fx = df[df['Asset_Class'] == 'FX']
    df_eq = df[df['Asset_Class'] == 'Eq']

    fx = _fx_delta(df_fx)     # no scenario dependence (single ρ, no cross-bucket)

    best_total, best_sc, best_eq = -1.0, None, 0.0
    for name, corr in CORR_SCENARIOS.items():
        eq    = _equity_delta(df_eq, corr['same_bucket'], corr['cross_bucket'])
        total = fx + eq
        if total > best_total:
            best_total, best_sc, best_eq = total, name, eq

    return DeltaResult(
        fx_charge     = fx,
        equity_charge = best_eq,
        scenario_used = best_sc or 'n/a',
        total         = best_total,
    )
