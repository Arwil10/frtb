"""
Testy jednostkowe dla sa/curvature.py — zakotwiczone w MAR21.5(2).
"""
import pytest
from pricing.black_scholes import BSOption
from sa.curvature import _compute_cvr, _psi, _bucket_K


def _make_opt(notional=1000.0, cp='call', bucket='B8'):
    """Helper — ATM equity call z typowymi parametrami."""
    return BSOption(
        id=1, asset_class='Eq', bucket=bucket, underlying='TEST',
        S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20, q=0.0,
        cp=cp, notional=notional,
    )


# ------------------------------------------------------------------ _psi
def test_psi_both_negative_returns_zero():
    """MAR21.5(3): ψ = 0 gdy oba CVR ujemne."""
    assert _psi(-1.0, -0.5) == 0.0

def test_psi_mixed_returns_one():
    """MAR21.5(3): ψ = 1 gdy jeden dodatni."""
    assert _psi(1.0, -0.5) == 1.0

def test_psi_both_positive_returns_one():
    assert _psi(1.0, 0.5) == 1.0


# ------------------------------------------------------------------ _compute_cvr
def test_cvr_long_call_worst_negative():
    """
    Długa call ma gamma > 0 (wypukłość działa na korzyść).
    CVR < 0 — brak wymogu kapitałowego z tytułu curvature.
    MAR21.5(3): max(CVR, 0)² = 0 dla ujemnych CVR.
    """
    opt = _make_opt(notional=1000.0, cp='call')
    up, dn = _compute_cvr(opt)
    assert max(up, dn) < 0, "Długa call powinna mieć CVR < 0 (wypukłość)"

def test_cvr_short_call_worst_positive():
    """
    Krótka call ma gamma < 0 (wklęsłość generuje ryzyko).
    CVR > 0 — wymóg kapitałowy z tytułu curvature.
    """
    opt = _make_opt(notional=-1000.0, cp='call')
    up, dn = _compute_cvr(opt)
    assert max(up, dn) > 0, "Krótka call powinna mieć CVR > 0 (wklęsłość)"

def test_cvr_long_short_opposite_signs():
    """Long i short mają przeciwne znaki CVR — symetria pozycji."""
    long_  = _make_opt(notional= 1000.0)
    short_ = _make_opt(notional=-1000.0)
    up_l, dn_l = _compute_cvr(long_)
    up_s, dn_s = _compute_cvr(short_)
    assert max(up_l, dn_l) * max(up_s, dn_s) < 0

def test_cvr_zero_rw_gives_zero():
    """Przy RW=0 szok = 0, więc CVR = 0 z definicji."""
    from unittest.mock import patch
    opt = _make_opt()
    with patch('sa.curvature.CURVATURE_SHOCK', {'B8': 0.0}):
        up, dn = _compute_cvr(opt)
    assert abs(up) < 1e-10
    assert abs(dn) < 1e-10


# ------------------------------------------------------------------ _bucket_K
def test_bucket_K_single_positive_cvr():
    """Jeden dodatni CVR — K_b = CVR."""
    k = _bucket_K([5.0], rho=0.25)
    assert abs(k - 5.0) < 1e-10

def test_bucket_K_all_negative_returns_zero():
    """MAR21.5(3): max(CVR_k, 0)² = 0 gdy wszystkie ujemne, cross też 0."""
    k = _bucket_K([-3.0, -2.0], rho=0.25)
    assert k == 0.0

def test_bucket_K_nonnegative():
    """K_b >= 0 zawsze."""
    k = _bucket_K([1.0, -5.0, 2.0], rho=0.50)
    assert k >= 0.0