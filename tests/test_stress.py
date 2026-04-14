# tests/test_stress.py
from pricing.black_scholes import BSOption
from sa.curvature import compute_curvature_charge
from sa.vega import compute_vega_charge

def test_empty_portfolio():
    """Pusty portfel -> 0."""
    assert compute_curvature_charge([]).total == 0.0
    assert compute_vega_charge([]).total == 0.0

def test_zero_sigma_curvature():
    """Opcja z sigma→0 nie powinna crashować."""
    opt = BSOption(
        id=99, asset_class='Eq', bucket='B8', underlying='TEST',
        S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.001, q=0.0,
        cp='call', notional=1000.0,
    )
    result = compute_curvature_charge([opt])
    assert result.total >= 0.0

def test_fully_offset_portfolio():
    """Long + short tej samej opcji -> CVR ≈ 0."""
    long_  = BSOption(id=1, asset_class='Eq', bucket='B8', underlying='T',
                      S=100, K=100, T=1, r=0.05, sigma=0.2, q=0,
                      cp='call', notional=1000.0)
    short_ = BSOption(id=2, asset_class='Eq', bucket='B8', underlying='T',
                      S=100, K=100, T=1, r=0.05, sigma=0.2, q=0,
                      cp='call', notional=-1000.0)
    result = compute_curvature_charge([long_, short_])
    assert result.total == 0.0