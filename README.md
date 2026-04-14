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

> **Note:** Actual numbers are mock-data driven. See `main.py` for the capital cliff report output.

## 🔍 Pipeline Flow
