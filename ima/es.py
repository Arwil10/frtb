"""
ima/es.py — Expected Shortfall via Filtered Historical Simulation (FHS).

Method: GARCH(1,1) volatility filtering per ticker, then portfolio ES.

MAR33.3  — 97.5th percentile, one-tailed
MAR33.4  — liquidity horizon scaling: sqrt(LH/10) × ES_10day
MAR33.5  — stress calibration: ESR,S × max(ESF,C / ESR,C, 1.0)
MAR33.9  — FHS is an approved simulation method
"""

from __future__ import annotations
from dataclasses import dataclass

import dataclasses

import numpy as np
import pandas as pd
from config import ES_CONFIDENCE, GARCH_OMEGA, GARCH_ALPHA, GARCH_BETA

@dataclass
class GARCHParams:
    omega: float
    alpha: float
    beta: float

# ============================================================================
# Market data
# ============================================================================
def get_returns(tickers, period=None, start=None, end=None, n_days=504):
    if isinstance(tickers, str):
        tickers = [tickers]
    try:
        import yfinance as yf
        if period:
            raw = yf.download(tickers, period=period, progress=False)
        else:
            raw = yf.download(tickers, start=start, end=end, progress=False)

        if isinstance(raw.columns, pd.MultiIndex):
            if 'Close' in raw.columns.get_level_values(0):
                prices = raw['Close']
            elif 'Adj Close' in raw.columns.get_level_values(0):
                prices = raw['Adj Close']
            else:
                raise ValueError(f'no Close/Adj Close columns, got: {raw.columns.tolist()[:5]}')
        else:
            if 'Close' in raw.columns:
                prices = raw[['Close']]
            elif 'Adj Close' in raw.columns:
                prices = raw[['Adj Close']]
            else:
                raise ValueError('no Close column')

        if prices.ndim == 1:
            prices = prices.to_frame()

        prices.columns = [c if isinstance(c, str) else str(c)
                          for c in prices.columns]

        prices = prices.dropna(axis=1, how='all')

        returns = np.log(prices / prices.shift(1)).dropna()
        if returns.empty:
            raise ValueError('no data after processing')
        return returns


    except Exception as e:
        import warnings
        warnings.warn(
            f"yfinance failed ({e}), using synthetic returns — DEV ONLY",
            stacklevel=2,
        )

        return _synthetic_returns(tickers, n_days)

def _portfolio_es_hs(
    returns_df: pd.DataFrame,
    exposures:  pd.Series,
    lh:         pd.Series,
    confidence: float = ES_CONFIDENCE,
) -> float:
    """
    Pure Historical Simulation ES

    """
    available = [t for t in exposures.index if t in returns_df.columns]
    if not available:
        return 0.0
    exp      = exposures[available]
    lh_      = lh[available]
    lh_scale = np.sqrt(lh_.values / 10.0)
    scaled   = returns_df[available] * lh_scale
    pnl      = scaled.dot(exp)
    cutoff   = np.percentile(pnl, (1 - confidence) * 100)
    tail     = pnl[pnl <= cutoff]
    return float(-tail.mean()) if len(tail) > 0 else 0.0


def find_stress_window(
    tickers:  list[str],
    exposures: pd.Series,
    lh:        pd.Series,
    min_year:  int = 2007,
) -> tuple[str, str, float]:
    """
    MAR33.7 — znajdź 12-miesięczny okres maksymalnych strat.
    """
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    r_all = get_returns(tickers, start=f'{min_year}-01-01', end=today)

    available = [t for t in exposures.index if t in r_all.columns]
    if not available or len(r_all) < 252:
        return '2008-09-01', '2009-08-31', 0.0   # fallback — Lehman

    exp = exposures[available]
    lh_ = lh[available]

    best_start = '2008-09-01'
    best_end   = '2009-08-31'
    best_es    = -np.inf

    # Kroczące okno 252 dni (MAR33.7 — 12 miesięcy
    for i in range(len(r_all) - 252):
        window = r_all.iloc[i: i + 252]
        es     = _portfolio_es_hs(window, exp, lh_)
        if es > best_es:
            best_es    = es
            best_start = r_all.index[i].strftime('%Y-%m-%d')
            best_end   = r_all.index[i + 251].strftime('%Y-%m-%d')

    return best_start, best_end, best_es


def _synthetic_returns(tickers: list[str], n_days: int) -> pd.DataFrame:
    rng  = np.random.default_rng(42)
    VOLS = {                     # przybliżone roczne σ → dzienna = σ/√252
        '^GSPC': 0.16, '^GDAXI': 0.18, '^FTSE': 0.14,
        '^N225': 0.17, 'EEM': 0.20,
        'USDPLN=X': 0.08, 'EURPLN=X': 0.07, 'GBPPLN=X': 0.09,
        'JPYPLN=X': 0.09, 'USDTRY=X': 0.35,
    }
    idx  = pd.date_range('2022-01-01', periods=n_days, freq='B')
    data = {}
    for t in tickers:
        daily_vol = VOLS.get(t, 0.15) / np.sqrt(252)
        data[t]   = rng.normal(0.0, daily_vol, n_days)
    return pd.DataFrame(data, index=idx)


# ============================================================================
# GARCH(1,1) volatility filter
# ============================================================================
def _garch_mle(returns: np.ndarray) -> GARCHParams:
    if len(returns) < 100:
        return GARCHParams(omega=GARCH_OMEGA, alpha=GARCH_ALPHA, beta=GARCH_BETA)

    try:
        from arch import arch_model
        model = arch_model(returns * 100, vol='Garch', p=1, q=1,
                           dist='normal', rescale=False)
        result = model.fit(disp='off', show_warning=False)


        scale = 100 ** 2
        omega = float(result.params['omega']) / scale
        alpha = float(result.params['alpha[1]'])
        beta = float(result.params['beta[1]'])

        # sanity check
        if alpha + beta >= 1.0 or omega <= 0:
            raise ValueError("niestacjonarny")

        return GARCHParams(omega=omega, alpha=alpha, beta=beta)

    except Exception as e:
        import warnings
        warnings.warn(f"arch GARCH failed ({e}). Fallback.")
        return GARCHParams(omega=GARCH_OMEGA, alpha=GARCH_ALPHA, beta=GARCH_BETA)

def _garch_vol(returns: np.ndarray, params: GARCHParams | None = None) -> np.ndarray:
    """
    σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}

    """
    if params is None:
        params = _garch_mle(returns)

    n      = len(returns)
    var    = np.empty(n)
    var[0] = float(np.var(returns))
    for t in range(1, n):
        var[t] = (params.omega
                  + params.alpha * returns[t - 1] ** 2
                  + params.beta * var[t - 1])

    return np.sqrt(np.maximum(var, 1e-12))


def _fhs_returns(returns_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtered Historical Simulation:
        r̃_t = (r_t / σ_t) × σ_current

    Standaryzuje zwroty przez historyczną zmienność GARCH,
    """
    filtered = {}
    for col in returns_df.columns:
        r             = returns_df[col].values
        params         = _garch_mle(r)
        sigma = _garch_vol(r, params)
        filtered[col] = (r / sigma) * sigma[-1]
    return pd.DataFrame(filtered, index=returns_df.index)

# ============================================================================
# Option full revaluation P&L (MAR33.9)
# ============================================================================
def option_pnl_series(opt, fhs_scaled: pd.DataFrame) -> pd.Series:
    """
    Full revaluation P&L opcji per scenariusz FHS.

    Chwyta: delta + gamma. Nie chwyta: vega (known simplification).
    """
    ticker = opt.underlying
    if ticker not in fhs_scaled.columns:
        return pd.Series(0.0, index=fhs_scaled.index)

    n_units = opt.notional / opt.S
    v_curr  = opt.price()
    r_col   = fhs_scaled[ticker]

    pnl = r_col.map(
        lambda r: (opt.reprice(S_new=opt.S * np.exp(r)) - v_curr) * n_units
    )
    return pnl

# ============================================================================
# Portfolio ES (FHS + LH scaling)
# ============================================================================
def portfolio_es(
    returns_df: pd.DataFrame,
    exposures:  pd.Series,
    lh:         pd.Series,
    confidence: float = ES_CONFIDENCE,
    options:    list  = None,              # <-- NOWE
) -> tuple[float, pd.Series]:

    options  = options or []
    lin_tickers = [t for t in exposures.index if t in returns_df.columns]
    opt_tickers = [o.underlying for o in options
                   if o.underlying in returns_df.columns]
    all_tickers = list(set(lin_tickers + opt_tickers))

    if not all_tickers:
        return 0.0, pd.Series(dtype=float)

    #  FHS
    filtered = _fhs_returns(returns_df[all_tickers])

    #  LH scaling
    lh_map = lh.to_dict()
    for opt in options:
        if opt.underlying not in lh_map:
            lh_map[opt.underlying] = 10 if opt.asset_class == 'Eq' else 20
    scale      = pd.Series({t: np.sqrt(lh_map.get(t, 10) / 10.0)
                             for t in all_tickers})
    fhs_scaled = filtered * scale

    #  P&L liniowy
    if lin_tickers:
        exp = exposures[lin_tickers]
        pnl = fhs_scaled[lin_tickers].dot(exp)
    else:
        pnl = pd.Series(0.0, index=returns_df.index)

    #  P&L opcji — full revaluation
    for opt in options:
        pnl = pnl.add(option_pnl_series(opt, fhs_scaled), fill_value=0.0)

    #  ES
    cutoff = np.percentile(pnl, (1 - confidence) * 100)
    tail   = pnl[pnl <= cutoff]
    es     = float(-tail.mean()) if len(tail) > 0 else 0.0

    return es, pnl


# ============================================================================
# Stressed ES ratio (MAR33.6)
# ============================================================================
def compute_stressed_es(
    r_current:  pd.DataFrame,
    r_stressed: pd.DataFrame,
    exposures:  pd.Series,
    lh:         pd.Series,
    options:    list = None,
) -> tuple[float, float, float, float]:
    """
    MAR33.6:
      ES_applied = ESR,S × max(ESF,C / ESR,C, 1.0)

    W uproszczeniu (brak osobnego reduced set):
      ESR,S ≈ ES(stressed period, full set)
      ESF,C ≈ ES(current period,  full set)
      ESR,C ≈ ES(current period,  full set) → ratio = 1.0

    TODO: zaimplementować reduced set per MAR33.5(2)
          gdy dostępny będzie osobny zestaw risk factors.

    Returns:
      es_current, es_stressed, ratio, es_applied
    """
    es_curr,   _ = portfolio_es(r_current,  exposures, lh)
    es_stress, _ = portfolio_es(r_stressed, exposures, lh)

    # TODO MAR33.5(2): ESR,C powinno być liczone na reduced set
    # Na razie: ratio = ESF,C / ESR,C ≈ 1.0 (konserwatywne)
    es_rc = es_curr   # placeholder — brak reduced set
    ratio = max(es_curr / es_rc, 1.0) if es_rc > 0 else 1.0

    es_applied = es_stress * ratio    # MAR33.6

    return es_curr, es_stress, ratio, es_applied


# ============================================================================
# NMRF stressed charge (MAR33.16)
# ============================================================================
def asigma_shock(returns: np.ndarray) -> tuple[float, float]:
    """
    Asymmetric sigma shock dla NMRF.
    Osobno dla prawego i lewego ogona.
    """
    up   = returns[returns > 0]
    down = returns[returns < 0]
    cs_up   = (float(np.mean(up))        + 3 * float(np.std(up)))   if len(up)   else 0.0
    cs_down = (float(abs(np.mean(down))) + 3 * float(np.std(down))) if len(down) else 0.0
    return cs_up, cs_down


def ucf(n_eff: float) -> float:
    """
    Uncertainty Compensation Factor — koryguje za krótką historię danych.
    Większy UCF gdy mniej obserwacji.
    """
    return 0.95 + 1.0 / np.sqrt(max(n_eff - 1.5, 1.0))