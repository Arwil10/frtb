"""
config.py — centralized FRTB regulatory parameters (BCBS d457).

Single source of truth for all risk weights, correlations, thresholds.
Previously duplicated across sa_engine / vega_charge / curvature_charge.
"""

# ============================================================================
# Global constants
# ============================================================================
CONVERSION_FACTOR = 12.5        #
OUTPUT_FLOOR      = 0.725       #


# ============================================================================
# SBM delta / vega risk weights (d457 §55, §99)
# ============================================================================
FX_DELTA_RW = 0.15              # MAR 21.87
FX_CORR     = 0.60              # MAR 21.89

EQUITY_DELTA_RW = {
    'B1': 0.55, 'B2': 0.60, 'B3': 0.45, 'B4': 0.55,
    'B5': 0.30, 'B6': 0.35, 'B7': 0.40, 'B8': 0.50,
    'B9': 0.70,
    'B10': 0.50, 'B11': 0.70,
    'B12': 0.15, 'B13': 0.25,
}                                   # MAR 21.77

VEGA_RW = {
    'FX': 1.00,                     # MAR 21.92
    'B12': 0.7778,                 # MAR 21.92
    'B13': 0.7778,                 # MAR 21.92
}


# ============================================================================
# Curvature risk weights (d457 §109–110)
# ============================================================================
# Curvature shocks equal delta risk weights (§109).
CURVATURE_SHOCK = {
    'FX': FX_DELTA_RW,
    'B12': EQUITY_DELTA_RW['B12'],
    'B13': EQUITY_DELTA_RW['B13'],
}


# ============================================================================
# Correlation scenarios for SBM aggregation DO NAPRAWY!!!!!!!!!!!!!!!!
# ============================================================================
# Banks must compute charges under three scenarios and take the max.
def _scenarios(same: float, cross: float) -> dict:
    """MAR21.6: trzy scenariusze korelacji."""
    return {
        'medium': {'same_bucket': same,                        'cross_bucket': cross},
        'high':   {'same_bucket': min(same * 1.25, 1.0),      'cross_bucket': min(cross * 1.25, 1.0)},   # MAR21.6(2)
        'low':    {'same_bucket': max(2*same-1, 0.75*same),   'cross_bucket': max(2*cross-1, 0.75*cross)}, # MAR21.6(3)
    }

CORR_SCENARIOS = _scenarios(same=0.25, cross=0.15)  # MAR21.78, MAR21.80
FX_CORR = 0.60  # MAR21.89 — bazowa, scenariusze liczone dynamicznie w delta.py
CORR_SCENARIOS_EQ = _scenarios(same=0.25, cross=0.15)  # MAR21.78, MAR21.80
CORR_SCENARIOS_FX = _scenarios(same=0.0,  cross=0.60)  # MAR21.89
# ============================================================================
# IMA parameters (d457 §181–191)
# ============================================================================
ES_CONFIDENCE   = 0.975
MC_MULTIPLIER   = 1.5           # baseline internal model multiplier (m_c)


DRC_CONFIDENCE  = 0.999         # MAR 33.20
DRC_N_SIM       = 100_000        # minimum viable due to computational constraints and confidence level
DRC_HORIZON_Y   = 1.0


# ============================================================================
# SA DRC (MAR22) —
# ============================================================================

SA_DRC_LGD = {
    'equity':       1.00,   # MAR22.12(1)
    'non_senior':   1.00,   # MAR22.12(1)
    'senior':       0.75,   # MAR22.12(2)
    'covered_bond': 0.25,   # MAR22.12(3)
}

SA_DRC_RW_NON_SEC = {       # MAR22.24 Table 2
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

SA_DRC_RW_BUCKET = {
    'IG': 0.060,   # BBB — najgorsza waga w IG
    'HY': 0.500,   # CCC — najgorsza waga w HY
    'D':  1.000,
    'NR': 0.150,
}

SA_DRC_MATURITY_FLOOR = 0.25    # MAR22.18: floor at 3 months = 1/4 year

# ============================================================================
# IMA DRC (MAR33) — wyłącznie parametry internal models approach
# ============================================================================

IMA_DRC_CONFIDENCE   = 0.999    # MAR33.20(5): 99.9% one-tailed
IMA_DRC_HORIZON_Y    = 1.0      # MAR33.20(5): one-year horizon
IMA_DRC_HORIZON_EQ_Y = 60/252   # MAR33.20(4): opcjonalnie 60 dni dla equity
IMA_DRC_PD_FLOOR     = 0.0003   # MAR33.24(2): floor 0.03%
IMA_DRC_CALIB_YEARS  = 10       # MAR33.27(4): min. 10 lat kalibracji

# PD używane w IMA DRC (MAR33.37) — kalibracja wewnętrzna banku,
# wartości poniżej to ZAŁOŻENIA MODELOWE, nie normy regulacyjne
# UŻYTO METODY SOVEREIGN PROXY
IMA_DRC_PD_INTERNAL = {
    'AAA': 0.0001,   # ← 0.01% sovereign AAA
    'AA+': 0.0002,
    'AA':  0.0002,   # ← 0.02% sovereign AA
    'AA-': 0.0003,
    'A+':  0.0005,   # ← 0.05% sovereign A+
    'A':   0.0007,
    'A-':  0.0011,
    'BBB+':0.0015, 'BBB': 0.0020, 'BBB-':0.0030,
    'BB+': 0.0060, 'BB':  0.0100, 'BB-': 0.0180,
    'B+':  0.0250, 'B':   0.0300, 'B-':  0.0500,
    'CCC': 0.1000, 'CC':  0.1500, 'C':   0.2500,
    'D':   1.0000, 'NR':  0.1500,
}
# Korelacje IMA DRC (MAR33.20, MAR33.27) — ZAŁOŻENIA MODELOWE,
# Basel nie przepisuje wartości liczbowych; kalibracja z danych rynkowych
IMA_DRC_RHO_INTERNAL = {
    'IG': 0.75,
    'HY': 0.50,
    'EM': 0.20,
}

EM_SECTORS = {'index_em'}


# ============================================================================
# PLAT thresholds (d457 §162)
# ============================================================================
PLAT_SPEARMAN_PASS  = 0.80
PLAT_SPEARMAN_AMBER = 0.70
PLAT_KS_PASS        = 0.05
PLAT_KS_AMBER       = 0.01
PLAT_WINDOW_DAYS    = 250
PLAT_KS_PASS_STAT  = 0.09   # MAR32.42(1)(b) — green: D < 0.09
PLAT_KS_RED_STAT   = 0.12   # MAR32.42(2)    — red:   D > 0.12


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

# Backtesting (MAR32)
BT_WINDOW       = 250       # MAR32.18 — 250 dni tradingowych
BT_RED_99       = 12        # MAR32.19 — red: >12 wyjątków przy 99%
BT_RED_975      = 30        # MAR32.19 — red: >30 wyjątków przy 97.5%

BT_MULTIPLIER = {           # MAR32.9 Table 1
    0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50,
    5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92,
}
BT_MULTIPLIER_RED = 2.00    # MAR32.9 Table 1 — red zone

# Desk-level progi (MAR32.19)
BT_DESK_RED_99  = 12    # >12 → red
BT_DESK_RED_975 = 30    # >30 → red

# GARCH(1,1) parametry dla FHS (ima/es.py)
# α + β < 1 → stacjonarność procesu wariancji
GARCH_OMEGA = 1e-6   # długookresowy poziom wariancji
GARCH_ALPHA = 0.10   # waga ostatniego szoku (reakcja na rynek)
GARCH_BETA  = 0.85   # persistence zmienności
