"""
pricing/black_scholes.py — BS / Garman-Kohlhagen pricer with analytical greeks.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class BSOption:
    """European option (BS for equity, GK for FX)."""
    id:          int
    asset_class: Literal['FX', 'Eq']
    bucket:      str                    # 'FX' | 'B8' | 'B9'
    underlying:  str
    S:           float
    K:           float
    T:           float                  # years
    r:           float                  # domestic rate
    sigma:       float
    q:           float                  # dividend yield / foreign rate
    cp:          Literal['call', 'put']
    notional:    float                  # signed EUR market value of the
                                        # underlying exposure: notional = n_units × S.
                                        # To convert per-unit BS results to
                                        # portfolio-level EUR, multiply by
                                        # (notional / S).

    _d1: float = field(init=False, repr=False)
    _d2: float = field(init=False, repr=False)

    def __post_init__(self):
        vol_sqrt_t = self.sigma * np.sqrt(self.T)
        self._d1 = (np.log(self.S / self.K)
                    + (self.r - self.q + 0.5 * self.sigma ** 2) * self.T) / vol_sqrt_t
        self._d2 = self._d1 - vol_sqrt_t

    # ------------------------------------------------------------------ price
    def price(self) -> float:
        from scipy.stats import norm
        disc_q = np.exp(-self.q * self.T)
        disc_r = np.exp(-self.r * self.T)
        if self.cp == 'call':
            return self.S * disc_q * norm.cdf(self._d1) - self.K * disc_r * norm.cdf(self._d2)
        return self.K * disc_r * norm.cdf(-self._d2) - self.S * disc_q * norm.cdf(-self._d1)

    # ----------------------------------------------------------------- greeks
    def delta(self) -> float:
        from scipy.stats import norm
        disc_q = np.exp(-self.q * self.T)
        if self.cp == 'call':
            return disc_q * norm.cdf(self._d1)
        return disc_q * (norm.cdf(self._d1) - 1)

    def vega(self) -> float:
        """dV/dσ for an absolute change in σ of 1.0 (i.e. 100 vol pts)."""
        from scipy.stats import norm
        return self.S * np.exp(-self.q * self.T) * norm.pdf(self._d1) * np.sqrt(self.T)

    def gamma(self) -> float:
        from scipy.stats import norm
        return (np.exp(-self.q * self.T) * norm.pdf(self._d1)
                / (self.S * self.sigma * np.sqrt(self.T)))

    # --------------------------------------------------------------- reprice
    def reprice(self, S_new: float | None = None, sigma_new: float | None = None) -> float:
        """Price under shocked S and/or sigma (used by curvature charge)."""
        return BSOption(
            id=self.id, asset_class=self.asset_class, bucket=self.bucket,
            underlying=self.underlying,
            S=S_new if S_new is not None else self.S,
            K=self.K, T=self.T, r=self.r,
            sigma=sigma_new if sigma_new is not None else self.sigma,
            q=self.q, cp=self.cp, notional=self.notional,
        ).price()
