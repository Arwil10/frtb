# tests/test_properties.py
from sa.curvature import compute_curvature_charge
from sa.vega import compute_vega_charge
from portfolio.options import OPTIONS

def test_curvature_charge_nonnegative():
    """RWA >= 0 zawsze — wymóg kapitałowy nie może być ujemny."""
    result = compute_curvature_charge(OPTIONS)
    assert result.total >= 0.0

def test_vega_charge_nonnegative():
    result = compute_vega_charge(OPTIONS)
    assert result.total >= 0.0

