"""
config.py — centralized FRTB regulatory parameters (BCBS d457).

Single source of truth for all risk weights, correlations, thresholds.
Previously duplicated across sa_engine / vega_charge / curvature_charge.
"""

# ============================================================================
# Global constants
# ============================================================================
CONVERSION_FACTOR = 12.5   # MAR20.1: RWA = Capital × 12.5
OUTPUT_FLOOR      = 0.725  # CRR3 art. 89: 72.5% output floor


# ============================================================================
# SBM delta risk weights
# ============================================================================
FX_DELTA_RW = 0.15  # MAR21.87: jednolita waga dla wszystkich par FX

EQUITY_DELTA_RW = {  # MAR21.77, Table 10: wagi dla equity spot price
    'B1': 0.55, 'B2': 0.60, 'B3': 0.45, 'B4': 0.55,  # large, emerging
    'B5': 0.30, 'B6': 0.35, 'B7': 0.40, 'B8': 0.50,  # large, advanced
    'B9': 0.70,                                         # small, emerging
    'B10': 0.50, 'B11': 0.70,                          # small, advanced + other
    'B12': 0.15, 'B13': 0.25,                          # indices
}


# ============================================================================
# SBM vega risk weights
# ============================================================================
VEGA_RW = {  # MAR21.92, Table 13: RW = α × sqrt(LH/10), α=55%
    'FX':  1.00,    # LH=40  → sqrt(40/10) × 0.55 ≈ 1.00 (zaokrąglone do 100%)
    'B12': 0.7778,  # LH=20  → sqrt(20/10) × 0.55 ≈ 0.7778
    'B13': 0.7778,  # LH=20
}


# ============================================================================
# Curvature risk weights
# ============================================================================
CURVATURE_SHOCK = {  # MAR21.98: curvature RW = delta RW dla FX i equity
    'FX':  FX_DELTA_RW,
    'B12': EQUITY_DELTA_RW['B12'],
    'B13': EQUITY_DELTA_RW['B13'],
}


# ============================================================================
# Correlation scenarios (MAR21.6)
# ============================================================================
def _apply_scenario(rho: float, scenario: str) -> float:
    """MAR21.6: aplikuje scenariusz korelacji do pojedynczej wartości."""
    if scenario == 'medium': return rho
    if scenario == 'high':   return min(rho * 1.25, 1.0)           # MAR21.6(2)
    if scenario == 'low':    return max(2 * rho - 1.0, 0.75 * rho) # MAR21.6(3)
    raise ValueError(f"Nieznany scenariusz: {scenario}")


# Korelacje within-bucket per bucket — MAR21.78(2)
_EQ_RHO_BASE = {
    'B1': 0.15, 'B2': 0.15, 'B3': 0.15, 'B4': 0.15,  # MAR21.78(2)(a): large, emerging
    'B5': 0.25, 'B6': 0.25, 'B7': 0.25, 'B8': 0.25,  # MAR21.78(2)(b): large, advanced
    'B9': 0.075,                                        # MAR21.78(2)(c): small, emerging
    'B10': 0.125,                                       # MAR21.78(2)(d): small, advanced
    'B11': 0.00,                                        # MAR21.79: simple sum
    'B12': 0.80, 'B13': 0.80,                          # MAR21.78(2)(e): indices
}

# Cross-bucket gamma — MAR21.80
# Uproszczenie: płaskie 0.15 zamiast pełnej macierzy 13×13
_EQ_GAMMA_BASE = 0.15  # MAR21.80(1): buckety 1-10

CORR_SCENARIOS_EQ = {  # MAR21.78, MAR21.80
    scen: {
        'same_bucket':  {b: _apply_scenario(rho, scen) for b, rho in _EQ_RHO_BASE.items()},
        'cross_bucket': _apply_scenario(_EQ_GAMMA_BASE, scen),
    }
    for scen in ('low', 'medium', 'high')
}

CORR_SCENARIOS_FX = {  # MAR21.89: gamma=0.60, same_bucket nie dotyczy (każda para = osobny bucket)
    scen: {
        'same_bucket':  0.0,
        'cross_bucket': _apply_scenario(0.60, scen),
    }
    for scen in ('low', 'medium', 'high')
}

# Ogólny scenariusz dla vega i curvature — płaskie uproszczenie
CORR_SCENARIOS = {  # używany przez sa/vega.py i sa/curvature.py
    scen: {
        'same_bucket':  _apply_scenario(0.25, scen),
        'cross_bucket': _apply_scenario(0.15, scen),
    }
    for scen in ('low', 'medium', 'high')
}


# ============================================================================
# IMA — Expected Shortfall (MAR33)
# ============================================================================
ES_CONFIDENCE = 0.975  # MAR33.3: 97.5th percentile, one-tailed
MC_MULTIPLIER = 1.5    # MAR33.41: baseline multiplier m_c

# GARCH(1,1) parametry dla FHS (MAR33.9)
# α + β < 1 → stacjonarność procesu wariancji
GARCH_OMEGA = 1e-6  # długookresowy poziom wariancji
GARCH_ALPHA = 0.10  # waga ostatniego szoku
GARCH_BETA  = 0.85  # persistence zmienności


# ============================================================================
# IMA DRC (MAR33.20–33.27)
# ============================================================================
DRC_CONFIDENCE     = 0.999      # MAR33.20(5): 99.9% one-tailed
DRC_N_SIM          = 100_000    # min. viable — produkcja wymaga 1M+
DRC_HORIZON_Y      = 1.0        # MAR33.20(5): 1-year horizon

IMA_DRC_CONFIDENCE   = 0.999    # MAR33.20(5)
IMA_DRC_HORIZON_Y    = 1.0      # MAR33.20(5)
IMA_DRC_HORIZON_EQ_Y = 60/252   # MAR33.20(4): opcjonalnie 60 dni dla equity
IMA_DRC_PD_FLOOR     = 0.0003   # MAR33.24(2): floor 0.03%
IMA_DRC_CALIB_YEARS  = 10       # MAR33.27(4): min. 10 lat kalibracji

# PD — ZAŁOŻENIA MODELOWE, metoda sovereign proxy
# Basel nie przepisuje wartości — kalibracja wewnętrzna banku (MAR33.37)
IMA_DRC_PD_INTERNAL = {
    'AAA': 0.0001, 'AA+': 0.0002, 'AA':  0.0002, 'AA-': 0.0003,
    'A+':  0.0005, 'A':   0.0007, 'A-':  0.0011,
    'BBB+':0.0015, 'BBB': 0.0020, 'BBB-':0.0030,
    'BB+': 0.0060, 'BB':  0.0100, 'BB-': 0.0180,
    'B+':  0.0250, 'B':   0.0300, 'B-':  0.0500,
    'CCC': 0.1000, 'CC':  0.1500, 'C':   0.2500,
    'D':   1.0000, 'NR':  0.1500,
}

# Korelacje — ZAŁOŻENIA MODELOWE (MAR33.20, MAR33.27)
IMA_DRC_RHO_INTERNAL = {
    'IG': 0.75,
    'HY': 0.50,
    'EM': 0.20,
}

EM_SECTORS = {'index_em'}


# ============================================================================
# SA DRC (MAR22)
# ============================================================================
SA_DRC_LGD = {
    'equity':       1.00,  # MAR22.12(1)
    'non_senior':   1.00,  # MAR22.12(1)
    'senior':       0.75,  # MAR22.12(2)
    'covered_bond': 0.25,  # MAR22.12(3)
}

SA_DRC_RW_NON_SEC = {  # MAR22.24, Table 2
    'AAA':       0.005,
    'AA':        0.020,
    'A':         0.030,
    'BBB':       0.060,
    'BB':        0.150,
    'B':         0.300,
    'CCC':       0.500,
    'Unrated':   0.150,
    'Defaulted': 1.000,
}

SA_DRC_RW_BUCKET = {  # uproszczenie: worst-case per kategoria
    'IG': 0.060,  # BBB
    'HY': 0.500,  # CCC
    'D':  1.000,
    'NR': 0.150,
}

SA_DRC_MATURITY_FLOOR = 0.25  # MAR22.18: floor 3 miesiące = 0.25 roku


# ============================================================================
# Backtesting (MAR32)
# ============================================================================
BT_WINDOW       = 250   # MAR32.18: 250 dni tradingowych
BT_RED_99       = 12    # MAR32.19: red > 12 wyjątków przy 99%
BT_RED_975      = 30    # MAR32.19: red > 30 wyjątków przy 97.5%

BT_MULTIPLIER = {       # MAR32.9, Table 1
    0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50,
    5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92,
}
BT_MULTIPLIER_RED = 2.00  # MAR32.9: red zone

BT_DESK_RED_99  = 12  # MAR32.19
BT_DESK_RED_975 = 30  # MAR32.19


# ============================================================================
# PLAT (MAR32.34–44)
# ============================================================================
PLAT_SPEARMAN_PASS  = 0.80  # MAR32.42(1)(a)
PLAT_SPEARMAN_AMBER = 0.70  # MAR32.42(3)
PLAT_KS_PASS        = 0.05  # informacyjnie
PLAT_KS_AMBER       = 0.01  # informacyjnie
PLAT_WINDOW_DAYS    = 250   # MAR32.35
PLAT_KS_PASS_STAT   = 0.09  # MAR32.42(1)(b): green D < 0.09
PLAT_KS_RED_STAT    = 0.12  # MAR32.42(2):    red   D > 0.12


# ============================================================================
# Aliasy dla kompatybilności wstecznej — DO USUNIĘCIA po migracji
# ============================================================================
RATING_PD                            = IMA_DRC_PD_INTERNAL
IMA_DRC_RHO_SAME_BUCKET_SAME_SECTOR = IMA_DRC_RHO_INTERNAL
RATING_BUCKET = {
    **{r: 'IG' for r in ['AAA','AA+','AA','AA-','A+','A','A-','BBB+','BBB','BBB-']},
    **{r: 'HY' for r in ['BB+','BB','BB-','B+','B','B-','CCC','CC','C']},
    'D':  'D',
    'NR': 'NR',
}