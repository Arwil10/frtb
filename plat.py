"""
plat.py — P&L Attribution Test

Compares HPL vs RTPL over a 250-day window:
  - Spearman correlation     (>= 0.80 pass, >= 0.70 amber)
  - Kolmogorov-Smirnov p-val  (>= 0.05 pass, >= 0.01 amber)

Zones: pass / amber (both IMA-eligible) / fail (forced to SA).
"""

"""
plat.py — PLA test (MAR32.34–32.44).
"""
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import stats

from config import (
    PLAT_SPEARMAN_PASS, PLAT_SPEARMAN_AMBER,
    PLAT_KS_PASS_STAT,  PLAT_KS_RED_STAT,
    PLAT_WINDOW_DAYS,
)


# ============================================================================
# Result
# ============================================================================
@dataclass
class PLATResult:
    desk_id:        str
    spearman_corr:  float
    ks_stat:        float
    ks_pvalue:      float
    status:         Literal['pass', 'amber', 'fail']
    ima_eligible:   bool
    hpl_mean:       float
    rtpl_mean:      float
    hpl_std:        float
    rtpl_std:       float
    n_observations: int


# ============================================================================
# Mock P&L (DEV ONLY — replace with real HPL/RTPL in production)
# ============================================================================
def generate_mock_pnl(
    desk_id:  str,
    n:        int = PLAT_WINDOW_DAYS,
    seed:     int = 42,
    scenario: Literal['pass', 'amber', 'fail'] = 'pass',
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + hash(desk_id) % 1000)
    hpl = rng.normal(0.0, 1.0, size=n)

    if scenario == 'pass':
        rtpl = hpl + rng.normal(0, 0.15, size=n)
    elif scenario == 'amber':
        rtpl = 0.85 * hpl + rng.normal(0, 0.50, size=n)
    else:
        rtpl = 0.20 * hpl + rng.normal(0, 2.0, size=n) + rng.exponential(0.5, size=n)
    return hpl, rtpl


# ============================================================================
# Runner
# ============================================================================
def run_plat(
    desk_id: str,
    hpl:     np.ndarray,
    rtpl:    np.ndarray,
    verbose: bool = True,
) -> PLATResult:
    assert len(hpl) == len(rtpl), 'HPL and RTPL must have same length'

    if len(hpl) != PLAT_WINDOW_DAYS:          # MAR32.35
        raise ValueError(
            f"PLA test wymaga {PLAT_WINDOW_DAYS} obserwacji, otrzymano {len(hpl)}"
        )

    spearman, _      = stats.spearmanr(hpl, rtpl)   # MAR32.34(1), MAR32.36-38
    ks_stat, ks_pval = stats.ks_2samp(hpl, rtpl)    # MAR32.34(2), MAR32.39-41

    red_s   = spearman < PLAT_SPEARMAN_AMBER          # < 0.70  MAR32.42(2)
    red_k   = ks_stat  > PLAT_KS_RED_STAT             # > 0.12  MAR32.42(2)
    green_s = spearman >= PLAT_SPEARMAN_PASS           # >= 0.80 MAR32.42(1)(a)
    green_k = ks_stat  <= PLAT_KS_PASS_STAT           # <= 0.09 MAR32.42(1)(b)

    if red_s or red_k:        # MAR32.42(2) — wystarczy jeden test red
        status = 'fail'
    elif green_s and green_k: # MAR32.42(1) — oba testy muszą być green
        status = 'pass'
    else:                     # MAR32.42(3) — ani green ani red
        status = 'amber'

    result = PLATResult(
        desk_id        = desk_id,
        spearman_corr  = float(spearman),
        ks_stat        = float(ks_stat),
        ks_pvalue      = float(ks_pval),
        status         = status,
        ima_eligible   = status in ('pass', 'amber'),  # MAR32.44
        hpl_mean       = float(np.mean(hpl)),
        rtpl_mean      = float(np.mean(rtpl)),
        hpl_std        = float(np.std(hpl)),
        rtpl_std       = float(np.std(rtpl)),
        n_observations = len(hpl),
    )
    if verbose:
        _print(result)
    return result


# ============================================================================
# Display
# ============================================================================
_ICON = {'pass': '[PASS]', 'amber': '[AMBER]', 'fail': '[FAIL]'}


def _print(r: PLATResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"PLAT — Desk: {r.desk_id}   {_ICON[r.status]}")
    print(f"{'=' * 60}")
    print(f"  Observations : {r.n_observations}")
    print(f"  HPL:  mu={r.hpl_mean:7.4f}  sigma={r.hpl_std:.4f}")
    print(f"  RTPL: mu={r.rtpl_mean:7.4f}  sigma={r.rtpl_std:.4f}")
    print(f"  Spearman : {r.spearman_corr:.4f}  "
          f"(green>={PLAT_SPEARMAN_PASS}, red<{PLAT_SPEARMAN_AMBER})")
    print(f"  KS stat  : {r.ks_stat:.4f}  "
          f"(green<={PLAT_KS_PASS_STAT}, red>{PLAT_KS_RED_STAT})")
    print(f"  KS pval  : {r.ks_pvalue:.4f}  (informacyjnie)")
    print(f"  IMA eligible: {'YES' if r.ima_eligible else 'NO (forced SA)'}")
    print(f"{'=' * 60}")