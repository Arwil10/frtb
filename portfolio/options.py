"""
portfolio/options.py — option portfolio (FX + equity).
"""

from pricing.black_scholes import BSOption


OPTIONS: list[BSOption] = [
    # -------------------------------------------------------------- FX options
    BSOption(id=101, asset_class='FX', bucket='FX', underlying='USDPLN',
             S=4.05, K=4.10, T=0.50, r=0.055, sigma=0.10, q=0.053,
             cp='call', notional=20.0),
    BSOption(id=102, asset_class='FX', bucket='FX', underlying='EURPLN',
             S=4.28, K=4.20, T=0.25, r=0.038, sigma=0.08, q=0.053,
             cp='put',  notional=-10.0),
    BSOption(id=103, asset_class='FX', bucket='FX', underlying='GBPPLN',
             S=5.12, K=5.20, T=1.00, r=0.052, sigma=0.12, q=0.053,
             cp='call', notional=15.0),

    # ---------------------------------------------------------- equity options
    BSOption(id=201, asset_class='Eq', bucket='B8', underlying='^GSPC',
             S=5200.0, K=5000.0, T=0.50, r=0.055, sigma=0.18, q=0.013,
             cp='put',  notional=30.0),
    BSOption(id=202, asset_class='Eq', bucket='B8', underlying='^GDAXI',
             S=18200.0, K=18500.0, T=0.25, r=0.038, sigma=0.16, q=0.025,
             cp='call', notional=12.0),
    BSOption(id=203, asset_class='Eq', bucket='B9', underlying='EEM',
             S=42.0, K=40.0, T=0.75, r=0.055, sigma=0.22, q=0.025,
             cp='call', notional=8.0),
]
