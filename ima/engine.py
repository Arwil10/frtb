"""
ima/engine.py — IMA runner: ES (MRF) + NMRF + IMA-DRC.
"""

from dataclasses import dataclass
import numpy as np

from config import CONVERSION_FACTOR
from portfolio.desks import Desk
from portfolio.drc   import get_desk_drc_positions
from ima.es  import (get_returns, compute_stressed_es,
                     find_stress_window, asigma_shock, ucf)
from ima.drcima import run_ima_drc, IMADRCResult


@dataclass
class IMAResult:
    desk_id:       str
    es_current:    float
    es_stressed:   float
    es_applied:    float
    stress_start:  str       # MAR33.7 — dokumentacja okresu stress
    stress_end:    str       # MAR33.7
    nmrf_charge:   float
    capital_mrf:   float
    capital_nmrf:  float
    rwa_mrf:       float
    rwa_nmrf:      float
    rwa_market:    float
    ima_drc:       float
    rwa_drc:       float
    rwa_total:     float


def run_ima(desk: Desk, multiplier: float = 1.5, verbose: bool = True) -> IMAResult:
    df        = desk.positions
    mrf_rows  = df[df['Type'] == 'MRF']
    nmrf_rows = df[df['Type'] == 'NMRF']

    tickers = mrf_rows['Ticker'].tolist()
    exp     = mrf_rows.set_index('Ticker')['Exposure_EUR']
    lh      = mrf_rows.set_index('Ticker')['LH']

    # Current period — ostatnie 2 lata
    r_curr = get_returns(tickers, period='2y')

    # MAR33.7 — znajdź najgorszy 12-miesięczny okres od 2007
    if verbose:
        print(f"  Searching stress window (MAR33.7)...")
    stress_start, stress_end, _ = find_stress_window(tickers, exp, lh)
    if verbose:
        print(f"  Stress window: {stress_start} → {stress_end}")

    r_stress = get_returns(tickers, start=stress_start, end=stress_end)

    # MAR33.6 — stressed ES
    es_curr, es_stress, ratio, es_applied = compute_stressed_es(
        r_curr, r_stress, exp, lh
    )

    # NMRF — MAR33.16
    nmrf_charge = 0.0
    for _, row in nmrf_rows.iterrows():
        ret = get_returns([row['Ticker']], period='2y').squeeze()
        if ret.empty:
            continue
        n_eff        = len(ret) / 2.0
        up, down     = asigma_shock(ret.values)
        daily_shock  = max(up, down) * ucf(n_eff)
        nmrf_charge += abs(row['Exposure_EUR']) * daily_shock * np.sqrt(row['LH'])

    capital_mrf  = es_applied * multiplier    # MAR33.41
    capital_nmrf = nmrf_charge
    rwa_mrf      = capital_mrf  * CONVERSION_FACTOR
    rwa_nmrf     = capital_nmrf * CONVERSION_FACTOR
    rwa_market   = rwa_mrf + rwa_nmrf

    # IMA-DRC
    drc_positions = get_desk_drc_positions(desk.desk_id)
    drc_res: IMADRCResult = run_ima_drc(
        drc_positions, desk.desk_id, verbose=verbose
    )

    rwa_total = rwa_market + drc_res.rwa_total

    result = IMAResult(
        desk_id      = desk.desk_id,
        es_current   = es_curr,
        es_stressed  = es_stress,
        es_applied   = es_applied,
        stress_start = stress_start,
        stress_end   = stress_end,
        nmrf_charge  = nmrf_charge,
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


def _print(r: IMAResult) -> None:
    print(f"\n{'=' * 65}")
    print(f"IMA — Desk: {r.desk_id}")
    print(f"{'=' * 65}")
    print(f"  Stress window: {r.stress_start} → {r.stress_end}")  # MAR33.7
    print(f"  ES current:   {r.es_current:8.4f}")
    print(f"  ES stressed:  {r.es_stressed:8.4f}")
    print(f"  ES applied:   {r.es_applied:8.4f}")
    print(f"  NMRF charge:  {r.nmrf_charge:8.4f}")
    print(f"  RWA MR:       {r.rwa_market:8.4f}")
    print(f"  RWA DRC:      {r.rwa_drc:8.4f}")
    print(f"  {'-' * 40}")
    print(f"  RWA IMA TOTAL: {r.rwa_total:.4f} mln EUR")
    print(f"{'=' * 65}")
