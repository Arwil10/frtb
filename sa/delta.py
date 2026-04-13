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

from config import FX_DELTA_RW, EQUITY_DELTA_RW, CORR_SCENARIOS_FX, CORR_SCENARIOS_EQ
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
def _fx_delta(df: pd.DataFrame, gamma: float) -> float:
    """FX delta: WS_k = RW × exposure_k, aggregated with γ = 0.60 (MAR21.89)."""
    if df.empty:
        return 0.0

    k_by_bucket: dict[str, float] = {}
    s_by_bucket: dict[str, float] = {}

    for ccy_pair, group in df.groupby("Bucket"): #MAR21.86 every currency pair is its own bucket
        net_sk = group['Exposure_EUR'].sum()
        ws_k = net_sk * FX_DELTA_RW
        k_by_bucket[ccy_pair] = abs(ws_k)
        s_by_bucket[ccy_pair] = ws_k

    return cross_bucket_charge(k_by_bucket, s_by_bucket, gamma)


# ----------------------------------------------------------------- equity
def _equity_delta(df: pd.DataFrame, rho_same: float, rho_cross: float) -> float:
    """Equity delta: bucket-level SBM then cross-bucket with γ = rho_cross."""
    if df.empty:
        return 0.0
    k_by_bucket: dict[str, float] = {}
    s_by_bucket: dict[str, float] = {}
    for bucket, group in df.groupby('Bucket'): #MAR21.72 defines bucket structure (market cap × economy × sector)
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
    max over the three correlation scenarios MAR 21.6-MAR21.7
    """
    # Merge linear + option-delta-equivalents in a single DataFrame
    frames = [linear_df[['Asset_Class', 'Bucket', 'Exposure_EUR']]]
    if options:
        frames.append(pd.DataFrame(_option_delta_equivalents(options))
                      [['Asset_Class', 'Bucket', 'Exposure_EUR']])
    df = pd.concat(frames, ignore_index=True)

    df_fx = df[df['Asset_Class'] == 'FX']
    df_eq = df[df['Asset_Class'] == 'Eq']
#debug
    for o in options:
        print(f"{o.underlying}: delta={o.delta():.4f}  notional={o.notional}  delta_eq={o.notional * o.delta():.4f}")
    print(df_fx[['Bucket', 'Exposure_EUR']].to_string())

    best_total, best_sc, best_fx, best_eq = -1.0, None, 0.0, 0.0
    for name in ('low', 'medium', 'high'):
        fx = _fx_delta(df_fx, CORR_SCENARIOS_FX[name]['cross_bucket'])
        eq = _equity_delta(df_eq, CORR_SCENARIOS_EQ[name]['same_bucket'],
                           CORR_SCENARIOS_EQ[name]['cross_bucket'])
        total = fx + eq #MAR 21.7
        if total > best_total:
            best_total, best_sc, best_fx, best_eq = total, name, fx, eq

    return DeltaResult(
        fx_charge     = best_fx,
        equity_charge = best_eq,
        scenario_used = best_sc or 'n/a',
        total         = best_total,
    )
