"""
ima/engine.py — IMA runner: ES (MRF) + NMRF + IMA-DRC.

Pipeline per MAR33.41:
    IMA_capital = max(ES_t-1, 60d_avg × m) + SES_NMRF + DRC_IMA

Simplifications vs MAR33:
  - ES: no reduced set (MAR33.5(2)) — ratio fixed at 1.0
  - NMRF: single USDTRY flag, no RFET (MAR33.16–33.18)
  - NMRF: Is_Idiosyncratic flag hardcoded, not derived from RFET
  - DRC: single-factor Vasicek, no 12-week average (MAR33.22)
  - multiplier m: passed externally from bank-wide BT (MAR33.42)
"""

from dataclasses import dataclass
import numpy as np

from config import CONVERSION_FACTOR
from portfolio.desks import Desk
from portfolio.drc   import get_desk_drc_positions
from ima.es  import (get_returns, compute_stressed_es,
                     find_stress_window, asigma_shock, ucf)
from ima.drcima import run_ima_drc, IMADRCResult


# ============================================================================
# Result dataclass
# ============================================================================
@dataclass
class IMAResult:
    desk_id:       str
    es_current:    float   # ESF,C — current period, full set (MAR33.6)
    es_stressed:   float   # ESR,S — stressed period (MAR33.6)
    es_applied:    float   # ESR,S × max(ESF,C / ESR,C, 1.0) (MAR33.6)
    stress_start:  str     # MAR33.7: worst 12-month window start
    stress_end:    str     # MAR33.7: worst 12-month window end
    nmrf_charge:   float   # SES_NM — aggregate NMRF capital (MAR33.17)
    capital_mrf:   float   # ES_applied × m (MAR33.41)
    capital_nmrf:  float   # SES_NM (MAR33.17)
    rwa_mrf:       float   # capital_mrf × 12.5 (MAR33.46)
    rwa_nmrf:      float   # capital_nmrf × 12.5 (MAR33.46)
    rwa_market:    float   # rwa_mrf + rwa_nmrf
    ima_drc:       float   # DRC total (MAR33.18–33.37)
    rwa_drc:       float   # ima_drc × 12.5 (MAR33.46)
    rwa_total:     float   # rwa_market + rwa_drc


# ============================================================================
# NMRF helpers (MAR33.16–33.17)
# ============================================================================
def _compute_nmrf_charge(nmrf_rows, verbose: bool = False) -> float:
    """
    MAR33.16–33.17: aggregate stress scenario capital for non-modellable risk factors.

    Groups per MAR33.17:
      I+J — idiosyncratic (credit/equity): zero correlation → sqrt(Σ SES²)
      K   — all other NMRFs:              ρ=0.6 formula

    Simplification: I and J merged into single idiosyncratic group.
    Is_Idiosyncratic flag is hardcoded in portfolio data — not derived from RFET.
    """
    ses_idio   = []  # MAR33.17(1)(2): groups I+J, zero correlation
    ses_others = []  # MAR33.17(3):    group K, ρ=0.6

    for _, row in nmrf_rows.iterrows():
        ret = get_returns([row['Ticker']], period='2y').squeeze()
        if ret.empty:
            continue

        # MAR33.16: stress scenario calibrated to 97.5% over stress period
        n_eff       = len(ret) / 2.0
        up, down    = asigma_shock(ret.values)
        daily_shock = max(up, down) * ucf(n_eff)

        # MAR33.16(1): LH = max(prescribed LH per MAR33.12, 20 days)
        lh_nmrf = max(row['LH'], 20)

        # SES_k per single NMRF
        ses_k = abs(row['Exposure_EUR']) * daily_shock * np.sqrt(lh_nmrf)

        if row.get('Is_Idiosyncratic', False):
            ses_idio.append(ses_k)    # MAR33.16(2): zero correlation for idiosyncratic
        else:
            ses_others.append(ses_k)  # MAR33.17: ρ=0.6 aggregation

    return _aggregate_nmrf(ses_idio, ses_others)


def _aggregate_nmrf(ses_idio: list[float], ses_others: list[float]) -> float:
    """
    MAR33.17: SES_NM = sqrt(Σ ISES²_i + Σ ISES²_j)
                     + sqrt((ρ·Σ SES_k)² + (1-ρ²)·Σ SES_k²)
    where ρ = 0.6 (MAR33.17(4)).
    """
    # MAR33.17(1)(2): groups I+J — zero correlation
    cap_idio = (float(np.sqrt(np.sum(np.square(ses_idio))))
                if ses_idio else 0.0)

    # MAR33.17(3)(4): group K — ρ=0.6
    RHO = 0.6  # MAR33.17(4)
    if ses_others:
        arr        = np.asarray(ses_others)
        sum_ses    = float(arr.sum())
        sum_ses_sq = float((arr ** 2).sum())
        cap_others = float(np.sqrt(
            (RHO * sum_ses) ** 2 + (1 - RHO ** 2) * sum_ses_sq
        ))
    else:
        cap_others = 0.0

    return cap_idio + cap_others  # MAR33.17: total SES_NM


# ============================================================================
# Main IMA runner
# ============================================================================
def run_ima(desk: Desk, multiplier: float = 1.5, verbose: bool = True) -> IMAResult:
    """
    MAR33.41: IMA capital = ES_applied × m + SES_NMRF + DRC_IMA

    multiplier m passed from bank-wide backtesting result (MAR33.42).
    """
    df        = desk.positions
    mrf_rows  = df[df['Type'] == 'MRF']   # modellable risk factors
    nmrf_rows = df[df['Type'] == 'NMRF']# non-modellable risk factors (MAR33.16)
    options = desk.options

    tickers = mrf_rows['Ticker'].tolist()
    opt_tickers = list({o.underlying for o in options})
    all_tickers = list(set(tickers + opt_tickers))

    tickers = mrf_rows['Ticker'].tolist()
    exp     = mrf_rows.set_index('Ticker')['Exposure_EUR']
    lh      = mrf_rows.set_index('Ticker')['LH']

    # MAR33.8: current period — last 2 years (≥ 12 months per MAR33.8(2))
    r_curr = get_returns(all_tickers, period='2y')

    # MAR33.7: identify worst 12-month stress window since 2007
    if verbose:
        print(f"  Searching stress window (MAR33.7)...")
    stress_start, stress_end, _ = find_stress_window(tickers, exp, lh)
    if verbose:
        print(f"  Stress window: {stress_start} → {stress_end}")

    r_stress = get_returns(tickers, start=stress_start, end=stress_end)


    # MAR33.6: ES_applied = ESR,S × max(ESF,C / ESR,C, 1.0)
    # Simplification: ESR,C = ESF,C → ratio = 1.0 (no reduced set per MAR33.5(2))
    es_curr, es_stress, ratio, es_applied = compute_stressed_es(
        r_curr, r_stress, exp, lh, options=options
    )

    # MAR33.16–33.17: aggregate NMRF stress scenario capital
    capital_nmrf = _compute_nmrf_charge(nmrf_rows, verbose=verbose)  # SES_NM

    # MAR33.41: IMA capital for MRF = ES_applied × m
    capital_mrf = es_applied * multiplier  # MAR33.41: m from bank-wide BT (MAR33.42)
    rwa_mrf     = capital_mrf  * CONVERSION_FACTOR  # MAR33.46
    rwa_nmrf    = capital_nmrf * CONVERSION_FACTOR  # MAR33.46
    rwa_market  = rwa_mrf + rwa_nmrf

    # MAR33.18–33.37: IMA Default Risk Charge
    drc_positions = get_desk_drc_positions(desk.desk_id)
    drc_res: IMADRCResult = run_ima_drc(
        drc_positions, desk.desk_id, verbose=verbose
    )

    # MAR33.43: ACR = IMA(MRF) + IMA(NMRF) + DRC
    rwa_total = rwa_market + drc_res.rwa_total

    result = IMAResult(
        desk_id      = desk.desk_id,
        es_current   = es_curr,
        es_stressed  = es_stress,
        es_applied   = es_applied,
        stress_start = stress_start,
        stress_end   = stress_end,
        nmrf_charge  = capital_nmrf,
        capital_mrf  = capital_mrf,
        capital_nmrf = capital_nmrf,
        rwa_mrf      = rwa_mrf,
        rwa_nmrf     = rwa_nmrf,
        rwa_market   = rwa_market,
        ima_drc      = drc_res.drc_total,
        rwa_drc      = drc_res.rwa_total,
        rwa_total    = rwa_total,
    )

    if verbose:
        _print(result)
    return result


# ============================================================================
# Display
# ============================================================================
def _print(r: IMAResult) -> None:
    print(f"\n{'=' * 65}")
    print(f"IMA — Desk: {r.desk_id}")
    print(f"{'=' * 65}")
    print(f"  Stress window : {r.stress_start} → {r.stress_end}")  # MAR33.7
    print(f"  ES current    : {r.es_current:8.4f}   (ESF,C)")       # MAR33.6(a)
    print(f"  ES stressed   : {r.es_stressed:8.4f}   (ESR,S)")      # MAR33.6(1)
    print(f"  ES applied    : {r.es_applied:8.4f}   (ESR,S × ratio)")  # MAR33.6
    print(f"  Capital MRF   : {r.capital_mrf:8.4f}   (ES × m)")    # MAR33.41
    print(f"  Capital NMRF  : {r.capital_nmrf:8.4f}   (SES_NM)")   # MAR33.17
    print(f"  RWA MRF       : {r.rwa_mrf:8.4f}")                    # MAR33.46
    print(f"  RWA NMRF      : {r.rwa_nmrf:8.4f}")                   # MAR33.46
    print(f"  RWA DRC       : {r.rwa_drc:8.4f}")                    # MAR33.46
    print(f"  {'-' * 50}")
    print(f"  RWA IMA TOTAL : {r.rwa_total:.4f} mln EUR")           # MAR33.43
    print(f"{'=' * 65}")
