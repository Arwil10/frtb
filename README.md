# Basel-IV-FRTB-Capital-Engine

Educational prototype of a **FRTB (BCBS d457 / CRR3)** market risk capital engine running SA-TB and IMA in parallel with a 72.5% output floor.

---

# ⚖️ Basel IV / FRTB — Capital Engine (SA-TB + IMA)

A comprehensive Python implementation of the **Fundamental Review of the Trading Book** framework, covering both the Standardised Approach (SA-TB) and the Internal Models Approach (IMA), with backtesting, PLA testing, and the output floor.

## 📐 Overview

This repository contains an end-to-end FRTB pipeline that:

1. 📊 **Runs SA-TB** — Sensitivity-Based Method (delta, vega, curvature) + SA-DRC
2. 🧠 **Runs IMA** — Expected Shortfall via Filtered Historical Simulation with GARCH(1,1), NMRF stressed add-on, and IMA-DRC via Vasicek one-factor MC
3. 🔁 **Backtests (MAR32)** — desk-level and bank-wide, producing the regulatory multiplier *m*
4. 🧪 **PLA Test (MAR32.34–44)** — Spearman + KS on HPL vs RTPL
5. 🏦 **Applies the Output Floor (CRR3 art. 89)** — `max(IMA_aggregate, 72.5% × Σ SA)`
6. 📋 **Generates a capital cliff report** — per-desk IMA eligibility + final capital charge

## 🧮 Methodology

The core capital formula follows:

$$K = \max\left(\text{IMA}_{agg},\; 0.725 \times \sum_{desk} \text{SA}_{desk}\right)$$

Where each desk's IMA charge is:

$$\text{IMA}_{desk} = ES_{full} \times \frac{ES_{stressed}}{ES_{current}} + \text{SES}_{NMRF} + \text{DRC}_{IMA}$$

And the SA-TB charge uses the three-scenario SBM aggregation:

$$\text{SA-TB} = \text{SBM}(\delta, \nu, \kappa) + \text{SA-DRC}$$

## 📁 Repo Layout




## 🚀 Run

```bash
pip install numpy pandas scipy yfinance
python main.py
```

## 📊 Key Results (Illustrative)

The engine produces the following capital stack for the prototype portfolio (2 desks: FX + Equity):

| Component | Approach | Capital Charge |
| :--- | :--- | :--- |
| **Delta** | SA-TB | Included in SBM |
| **Vega** | SA-TB | Included in SBM |
| **Curvature** | SA-TB | Included in SBM |
| **SA-DRC** | SA-TB | Separate add-on |
| **ES (IMA)** | IMA | GARCH-filtered FHS |
| **IMA-DRC** | IMA | Vasicek MC, 99.9% |
| **Output Floor** | CRR3 art. 89 | `max(IMA, 72.5% × SA)` |



## 🔍 Pipeline Flow


## ⚠️ Known Simplifications

This is a **teaching prototype**, not production-grade software. Each item below is a deliberate shortcut and a compliance gap vs. BCBS d457 / CRR3.

| # | Area | Simplification | Standard Requirement |
| :--- | :--- | :--- | :--- |
| 1 | **Risk classes** | FX + Equity only | GIRR, CSR non-sec, CSR sec, CTP, Commodity missing |
| 2 | **Correlations** | Flat `(same=0.25, cross=0.15)` for all buckets | MAR21.78/80 per-bucket ρ_kl and γ_bc tables |
| 3 | **IMA-DRC PDs** | Sovereign proxy for equity index issuers | MAR33.24 obligor-level PDs from IRB/market data |
| 4 | **Index look-through** | `^GSPC` treated as one position | MAR22.5 decomposition into 500 single names |
| 5 | **Vasicek model** | Single-factor, flat ρ per rating bucket | Multi-factor, historically calibrated co-default |
| 6 | **DRC simulations** | `N_SIM = 100,000` (~100 tail obs.) | Production: 1M–10M, often with importance sampling |
| 7 | **GARCH calibration** | Hardcoded `ω=1e-6, α=0.10, β=0.85` for all factors | Per-ticker MLE fit |
| 8 | **Stressed ES ratio** | `es_rc = es_curr` → ratio always 1.0 | MAR33.5(2) reduced set, proper scaling |
| 9 | **Stress window search** | Pure HS on full set, Lehman fallback | MAR33.5(2) reduced set required |
| 10 | **NMRF** | Single `USDTRY` flag, no RFET | MAR33.16–18 aggregation + category split |
| 11 | **RFET** | None — MRF/NMRF split hardcoded | MAR31.12: 24+ real prices, max 30-day gap |
| 12 | **Backtesting** | `max(APL, HPL)` exceptions only | MAR32.5/32.18: separate APL and HPL counters |
| 13 | **BT / PLAT data** | Gaussian mock P&L | Production: front-office APL, frozen-portfolio HPL, risk-engine RTPL |
| 14 | **SA-DRC ratings** | Collapsed to IG/HY/D/NR (worst-case) | MAR22.24 Table 2 per-rating weights |
| 15 | **Option JtD** | Set to 0 (formally correct per MAR22.14) | Banks apply delta-equivalent hedge recognition |
| 16 | **Portfolio** | 2 desks, hardcoded positions | No CSV/Parquet loader; production: 100k+ trades |
| 17 | **Market data** | Silent fallback to `synthetic_returns(seed=42)` | Rate-limit should hard-fail, not silently substitute |
| 18 | **Testing** | No test suite | SR 11-7 / MAR10.8: mandatory model risk management |
| 19 | **Repo hygiene** | Mixed Polish/English, `.Rhistory` committed, TODO aliases in `config.py` | — |
| 20 | **PLA diagnostics** | Aggregate Spearman + KS only | Greek-level delta/vega explain, unexplained-P&L report |

## 🗺️ Minimum Viable Production Roadmap

- [ ] Add GIRR, CSR non-sec, Commodity to SBM
- [ ] Replace `CORR_SCENARIOS` with full MAR21 ρ_kl / γ_bc tables
- [ ] Wire real APL / HPL / RTPL into BT and PLAT
- [ ] Implement reduced set + MAR33.5(2)–33.6 ratio
- [ ] Per-ticker MLE GARCH fit + RFET
- [ ] IMA-DRC: multi-factor model, real ρ calibration, `N_SIM ≥ 1e6`
- [ ] Index look-through for equity (MAR22.5)
- [ ] Real data pipeline with validation and hard-fail on missing data
- [ ] Test suite + regulatory benchmark reconciliation
- [ ] Model documentation per SR 11-7: data, assumptions, limits, validation

## 📌 Current State

> End-to-end FRTB architecture demo with correct SBM and Vasicek formulas, but **mocked data**, **incomplete risk class coverage**, and **deliberately flat calibrations**.
> Suitable as a learning reference or interview demonstration — not for regulatory submission.

---

*Disclaimer: This project is for educational purposes only. It does not constitute regulatory-compliant capital calculation software. All calibrations and simplifications are documented above.*
