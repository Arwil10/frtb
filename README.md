# Analysis of Market Risk Capital Requirements under FRTB (Master's Thesis Project)

## Overview
This repository contains the computational engine developed for my Master's Thesis: **"Quantitative Comparison of Standardised and Internal Model Approaches under Basel IV"**. 

The goal of this research is to evaluate the sensitivity of the FRTB (Fundamental Review of the Trading Book) framework to different market regimes using a custom-built Python engine.

## Project Status: Work in Progress (Research Phase) 🏗️
The engine is currently used to generate numerical results for the comparative analysis chapter of my thesis.

### Key Features Implemented:
* **Standardised Approach (SA-TB):** Full SBM (Sensitivities-Based Method) for FX and Equity, including Delta, Vega, and Curvature risk charges.
* **Internal Models Approach (IMA):** Expected Shortfall (ES) engine using Filtered Historical Simulation (FHS) with GARCH(1,1) volatility scaling.
* **Default Risk Charge (DRC):** Implementation of both SA-DRC (bucket-based) and IMA-DRC (Vasicek One-Factor Monte Carlo).
* **Regulatory Compliance Tests:** Automated Backtesting (MAR32) and P&L Attribution (PLAT) tests to determine desk-level IMA eligibility.

## Research Roadmap & Methodological Scope
To maintain a focused research scope for the thesis, certain methodological choices were made:

### 1. Risk Class Coverage (Phase 1)
Currently focuses on **FX and Equity** classes. GIRR (Interest Rate) and CSR (Credit Spread) modules are planned for Phase 2 to analyze cross-asset correlation impacts under the 72.5% Output Floor.

### 2. Volatility Modelling (GARCH MLE)
The current FHS engine uses calibrated GARCH(1,1) parameters. A migration to Maximum Likelihood Estimation (MLE) for per-ticker parameter fitting is under development to improve ES accuracy during stress periods.

### 3. Credit Risk Parameters (DRC)
IMA-DRC currently utilizes a sovereign proxy for PD (Probability of Default). The research roadmap includes implementing a direct mapping to internal IRB (Internal Ratings-Based) models as per MAR33.24.

### 4. Computational Performance
The IMA-DRC module runs 100,000 simulations as a benchmark. Optimization for 1,000,000+ simulations using Importance Sampling is being evaluated for the final thesis results.

## Technical Stack
* **Language:** Python 3.x
* **Libraries:** NumPy, Pandas, SciPy (Optimization & Statistics).
* **Architecture:** Modular engine with centralized configuration (`config.py`) to ensure regulatory consistency across all risk modules.
