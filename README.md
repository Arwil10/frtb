├── main.py                # orchestrator — runs the full pipeline
├── config.py              # regulatory parameters (risk weights, correlations, liquidity horizons)
├── backtesting.py         # MAR32 desk-level and bank-wide VaR backtesting
├── plat.py                # MAR32.34–44 P&L attribution test
├── sa/
│   ├── delta.py           # delta SBM — FX & equity
│   ├── vega.py            # vega SBM — options vol sensitivities
│   ├── curvature.py       # curvature risk — BS re-pricing with the psi indicator
│   ├── drc.py             # SA-DRC — JtD × LGD × risk weight
│   ├── engine.py          # SA-TB orchestrator
│   └── _aggregation.py    # SBM bucket / cross-bucket aggregation
├── ima/
│   ├── es.py              # FHS-GARCH Expected Shortfall (MAR33)
│   ├── drcima.py          # IMA-DRC — Vasicek one-factor MC (MAR33.24)
│   └── engine.py          # IMA orchestrator (ES + SES_NMRF + DRC)
├── portfolio/
│   ├── linear.py          # linear positions (FX spots, equity)
│   ├── options.py         # BSOption dataclass + portfolio
│   ├── desks.py           # desk definitions
│   └── drc.py             # DRC position dataclass
├── pricing/
│   └── black_scholes.py   # Black-Scholes pricer (delta, vega, re-pricing)
└── tests/
    ├── test_corr_scenarios.py  # MAR21.6 correlation scenario ordering
    ├── test_curvature.py       # CVR logic, psi indicator, bucket_K (MAR21.5)
    ├── test_properties.py      # non-negativity and monotonicity
    └── test_stress.py          # edge cases: empty portfolio, zero sigma, full offset
