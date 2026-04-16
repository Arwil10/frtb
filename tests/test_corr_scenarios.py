"""
Testy scenariuszy korelacji — MAR21.6.
"""
from config import CORR_SCENARIOS, CORR_SCENARIOS_EQ, CORR_SCENARIOS_FX


# ------------------------------------------------------------------ CORR_SCENARIOS
def test_scenarios_have_three_keys():
    assert set(CORR_SCENARIOS.keys()) == {'low', 'medium', 'high'}

def test_high_geq_medium_geq_low_same_bucket():
    """MAR21.6: high >= medium >= low."""
    low    = CORR_SCENARIOS['low']['same_bucket']
    medium = CORR_SCENARIOS['medium']['same_bucket']
    high   = CORR_SCENARIOS['high']['same_bucket']
    assert high >= medium >= low

def test_high_capped_at_100pct():
    """MAR21.6(2): high nie przekracza 100%."""
    assert CORR_SCENARIOS['high']['same_bucket']  <= 1.0
    assert CORR_SCENARIOS['high']['cross_bucket'] <= 1.0

def test_low_nonnegative():
    """MAR21.6(3): korelacje nie mogą być ujemne."""
    assert CORR_SCENARIOS['low']['same_bucket']  >= 0.0
    assert CORR_SCENARIOS['low']['cross_bucket'] >= 0.0


# ------------------------------------------------------------------ CORR_SCENARIOS_EQ
def test_eq_same_bucket_is_dict():
    """CORR_SCENARIOS_EQ['medium']['same_bucket'] to słownik per bucket."""
    assert isinstance(CORR_SCENARIOS_EQ['medium']['same_bucket'], dict)

def test_eq_bucket_values_match_mar21_78():
    """MAR21.78(2): sprawdź kluczowe wartości bazowe."""
    medium = CORR_SCENARIOS_EQ['medium']['same_bucket']
    assert medium['B5'] == 0.25   # MAR21.78(2)(b): large, advanced
    assert medium['B1'] == 0.15   # MAR21.78(2)(a): large, emerging
    assert medium['B12'] == 0.80  # MAR21.78(2)(e): indices

def test_eq_high_geq_medium_per_bucket():
    """High >= medium dla każdego bucketu."""
    for b in CORR_SCENARIOS_EQ['medium']['same_bucket']:
        assert (CORR_SCENARIOS_EQ['high']['same_bucket'][b] >=
                CORR_SCENARIOS_EQ['medium']['same_bucket'][b])


# ------------------------------------------------------------------ CORR_SCENARIOS_FX
def test_fx_medium_cross_bucket():
    """MAR21.89: FX cross-bucket gamma = 0.60 w scenariuszu medium."""
    assert CORR_SCENARIOS_FX['medium']['cross_bucket'] == 0.60

def test_fx_same_bucket_zero():
    """FX — każda para to osobny bucket, same_bucket = 0."""
    assert CORR_SCENARIOS_FX['medium']['same_bucket'] == 0.0