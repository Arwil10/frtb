#  Basel IV / FRTB — Capital Engine (SA-TB + IMA)
 
Educational prototype of a **FRTB (BCBS d457 / CRR3)** market risk capital engine running SA-TB and IMA in parallel with a 72.5% output floor.
 
> **Disclaimer:** This project is for educational purposes only. It does not constitute regulatory-compliant capital calculation software. All calibrations and simplifications are documented below.
 
---
 
##  Overview
 
An end-to-end FRTB pipeline covering:
 
1. 📊 **SA-TB** — Sensitivity-Based Method (delta, vega, curvature) + SA-DRC
2. 🧠 **IMA** — Expected Shortfall via Filtered Historical Simulation with GARCH(1,1), NMRF stressed add-on, IMA-DRC via Vasicek one-factor Monte Carlo
3. 🔁 **Backtesting (MAR32)** — desk-level and bank-wide, producing the regulatory multiplier *m*
4. 🧪 **PLA Test (MAR32.34–44)** — Spearman ρ + KS statistic on HPL vs RTPL
5. 🏦 **Output Floor (CRR3)** — `max(IMA_aggregate, 72.5% × Σ SA)`
6. 📋 **Capital cliff report** — per-desk IMA eligibility + final capital charge
 
---
 
##  Repo Layout
 
```
├── main.py                  # Orchestrator — runs full pipeline
├── config.py                # All regulatory parameters (RWs, correlations, LHs)
├── backtesting.py           # MAR32 desk-level and bank-wide VaR backtesting
├── plat.py                  # MAR32.34–44 P&L attribution test
├── sa/
│   ├── delta.py             # Delta SBM — FX & Equity
│   ├── vega.py              # Vega SBM — options vol sensitivities
│   ├── curvature.py         # Curvature risk — BS re-pricing with ψ indicator
│   ├── drc.py               # SA-DRC — JtD × LGD × risk weight
│   ├── engine.py            # SA-TB orchestrator
│   └── _aggregation.py      # SBM bucket/cross-bucket aggregation primitives
├── ima/
│   ├── es.py                # FHS-GARCH Expected Shortfall (MAR33)
│   ├── drcima.py            # IMA-DRC — Vasicek one-factor MC (MAR33.24)
│   └── engine.py            # IMA orchestrator (ES + SES_NMRF + DRC)
├── portfolio/
│   ├── linear.py            # Linear positions (FX spots, equity)
│   ├── options.py           # BSOption dataclass + portfolio
│   ├── desks.py             # Desk definitions
│   └── drc.py               # DRC position dataclass
├── pricing/
│   └── black_scholes.py     # Black-Scholes pricer (delta, vega, re-pricing)
└── tests/
    ├── test_corr_scenarios.py   # MAR21.6 correlation scenario ordering
    ├── test_curvature.py        # CVR logic, ψ indicator, bucket_K (MAR21.5)
    ├── test_properties.py       # Non-negativity and monotonicity
    └── test_stress.py           # Edge cases: empty portfolio, zero sigma, full offset
```
 
---
 
##  Methodology
 
### Output Floor
 
$$K = \max\!\left(\text{IMA}_{agg},\; 0.725 \times \sum_{d} \text{SA}_{d}\right)$$
 
### IMA Desk Charge
 
$$\text{IMA}_{d} = \underbrace{ES_{F,C} \times \frac{ES_{R,S}}{ES_{R,C}} \times m}_{\text{Capital MRF}} + \underbrace{SES_{NMRF}}_{\text{NMRF add-on}} + \underbrace{DRC_{IMA}}_{\text{Vasicek MC}}$$
 
where $m$ is the backtesting multiplier from MAR32.9 Table 1 (1.5 in green zone).
 
### Expected Shortfall — FHS-GARCH (MAR33.3)
 
$$ES_{t} = -\frac{1}{T \cdot \alpha} \sum_{\tau: r_\tau < \text{VaR}_\alpha} r_\tau, \qquad \tilde{r}_\tau = \frac{\epsilon_\tau}{\hat{\sigma}_\tau} \cdot \hat{\sigma}_t$$
 
Returns are standardised by GARCH(1,1) conditional volatility, then re-scaled to current variance before the ES tail average — the Filtered Historical Simulation step.
 
### GARCH(1,1) Variance Process
 
$$\sigma_t^2 = \omega + \alpha\,\epsilon_{t-1}^2 + \beta\,\sigma_{t-1}^2$$
 
with hardcoded $\omega = 10^{-6}$, $\alpha = 0.10$, $\beta = 0.85$ (see Known Simplification #7).
 
### IMA-DRC — Vasicek One-Factor
 
$$L_i = \mathbf{1}\!\left[\sqrt{\rho_i}\,Z + \sqrt{1-\rho_i}\,\epsilon_i \leq \Phi^{-1}(PD_i)\right] \times JtD_i$$
 
$$DRC_{IMA} = \text{VaR}_{99.9\%}\!\left(\sum_i L_i\right)$$
 
Systematic factor $Z \sim \mathcal{N}(0,1)$, idiosyncratic $\epsilon_i \sim \mathcal{N}(0,1)$, $\rho_i$ per rating bucket (IG: 0.30, EM: 0.15).
 
### NMRF Stressed Add-On
 
$$SES_{NMRF} = \sqrt{\sum_{q} SES_q^2}, \qquad SES_q = ES_q^{RS} \times \sqrt{\frac{LH_q}{10}}$$
 
Liquidity horizon scaling under the square-root-of-time approximation.
 
### SA-TB — SBM Aggregation (MAR21.4)
 
**Within-bucket:**
 
$$K_b = \sqrt{\sum_k WS_k^2 + \rho_{kl} \sum_{k \neq l} WS_k \cdot WS_l}$$
 
**Cross-bucket:**
 
$$\text{SA-TB} = \max\!\left(\sqrt{\sum_b K_b^2 + \gamma_{bc} \sum_{b \neq c} S_b \cdot S_c},\; 0\right)$$
 
Three correlation scenarios (low / medium / high per MAR21.6) — worst case taken.
 
### Curvature CVR (MAR21.5)
 
$$CVR_k^{\pm} = -\!\left[\,V(x_k^{\pm}) - V(x_k) \mp RW_k^{curv} \cdot \delta_k\right]$$
 
$$K_b^{curv} = \sqrt{\max\!\left(\sum_k \max(CVR_k, 0)^2 + \rho_{kl}\sum_{k\neq l}\psi(CVR_k, CVR_l)\cdot CVR_k \cdot CVR_l,\; 0\right)}$$
 
where $\psi(CVR_k, CVR_l) = 0$ when both are negative (MAR21.5(3)).
 
---
 
##  Run
 
```bash
pip install numpy pandas scipy yfinance
python main.py
```
 
---
 
##  Key Results — Prototype Portfolio (FX + Equity desks)
 
All figures are illustrative — driven by mock data and hardcoded GARCH parameters.
 
### Capital Stack
 
| Component | Desk | Approach | RWA (mln EUR) |
| :--- | :--- | :--- | ---: |
| Delta + Vega + Curvature (SBM) | FX | SA-TB | included below |
| SA-DRC | FX | SA-TB | 0.00 |
| **SA-TB total** | **FX** | **SA-TB** | **239.43** |
| ES MRF (`m = 1.50`, stress window Jun 2008 – Jul 2009) | FX | IMA | 68.41 |
| SES NMRF (USDTRY, flagged) | FX | IMA | 7.34 |
| IMA-DRC | FX | IMA | 0.00 |
| **IMA total** | **FX** | **IMA** | **75.74** |
| Delta + Vega + Curvature (SBM) | Eq | SA-TB | included below |
| SA-DRC | Eq | SA-TB | 2.62 |
| **SA-TB total** | **Eq** | **SA-TB** | **209.41** |
| ES MRF (`m = 1.50`, stress window Sep 2007 – Dec 2008) | Eq | IMA | 186.57 |
| SES NMRF | Eq | IMA | 0.00 |
| IMA-DRC (Vasicek MC, 1 M sims, 99.9%) | Eq | IMA | 187.50 |
| **IMA total** | **Eq** | **IMA** | **374.07** |
 
### Backtesting & PLA Eligibility
 
| Desk | BT (99%) | BT status | Spearman ρ | KS stat | PLAT | Source used | Capital cliff |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | ---: |
| FX | 1 exc. | 🟢 GREEN | 0.105 | 0.292 | 🔴 FAIL | SA (PLAT fail) | +163.69 mln EUR |
| Eq | 0 exc. | 🟢 GREEN | 0.988 | 0.032 | 🟢 PASS | IMA | 0.00 |
 
Bank-wide BT: **GREEN** — 1 exception over 250 observations → multiplier **m = 1.50**.
 
### Final Capital
 
| | RWA (mln EUR) |
| :--- | ---: |
| Portfolio RWA (post BT/PLAT) | **613.49** |
| SA total (both desks) | 448.84 |
| Output floor (72.5% × SA) | 325.41 |
| Floor binding? | No (+288.09 above floor) |
| **RWA FINAL** | **613.49** |
| Capital cliff (FX PLAT failure) | **+163.69 mln EUR (+36.4% vs pure IMA)** |
 
> **Key insight:** The FX desk's PLAT failure (Spearman 0.105, KS 0.292) forces a switch from IMA (75.74 mln) to SA (239.43 mln), adding 163.69 mln EUR in capital — a concrete illustration of the IMA eligibility cliff under MAR32.
 
---
 
##  Pipeline Flow
 
```
portfolio/
  ├─ linear positions (FX spots, equity)
  └─ options (BSOption → Black-Scholes pricer)
         │
         ├──► SA-TB Engine ──────────────────────────────────────┐
         │      delta.py → SBM (FX + Eq buckets)                 │
         │      vega.py  → SBM (vol surface buckets)             │
         │      curvature.py → CVR re-pricing + ψ indicator      │
         │      drc.py → JtD × LGD × weight                      │
         │                                                        │
         ├──► IMA Engine ────────────────────────────────────────┤
         │      es.py → FHS-GARCH ES, stress window search       │
         │      drcima.py → Vasicek MC, VaR 99.9%                │
         │      NMRF flag → SES add-on                            │
         │                                                        │
         ├──► Backtesting (MAR32) ───────────────────────────────┤
         │      desk-level: green/red → IMA eligibility          │
         │      bank-wide: m multiplier                          │
         │                                                        │
         ├──► PLAT (MAR32.34–44) ────────────────────────────────┤
         │      Spearman ρ + KS(HPL, RTPL)                       │
         │      green/amber/red → IMA eligibility                │
         │                                                        │
         └──► Capital Aggregation ────────────────────────────────┘
               per-desk: IMA or SA (BT+PLAT gating)
               bank-wide: max(Σ IMA_desk, 72.5% × Σ SA_desk)
               capital cliff report
```
 
---
 
## ⚠️ Known Simplifications
 
This is a **teaching prototype**, not production-grade software. Each item is a deliberate shortcut and a documented compliance gap vs. BCBS d457 / CRR3.
 
| # | Area | Simplification | Standard requirement |
| :--- | :--- | :--- | :--- |
| 1 | **Risk classes** | FX + Equity only | GIRR, CSR non-sec, CSR sec non-CTP, CTP, Commodity missing |
| 2 | **Correlation scenarios** | Single flat ρ per risk class, hardcoded | MAR21 full ρ_kl / γ_bc lookup tables per bucket pair |
| 3 | **IMA-DRC PDs** | Sovereign proxy (IG floor 0.03%, EM 1.0%) for all equity index issuers | MAR33.24: obligor-level PDs from IRB models or market-implied data |
| 4 | **Index look-through** | `^GSPC`, `^GDAXI` etc. treated as single positions | MAR22.5: decomposition into constituent single names |
| 5 | **Vasicek model** | Single-factor, flat ρ per rating bucket (IG 0.30, EM 0.15) | Multi-factor Gaussian copula, historically calibrated co-default correlations |
| 6 | **DRC simulations** | `N_SIM = 100,000` (~100 tail observations) | Production: 1 M–10 M with importance sampling |
| 7 | **GARCH calibration** | Hardcoded `ω=1e-6, α=0.10, β=0.85` for all risk factors | MAR33.5: per-ticker MLE fit, parameter stability testing |
| 8 | **Stressed ES ratio** | `ES_R,S / ES_R,C` forced to 1.0 (i.e. `es_rc = es_curr`) | MAR33.5(2): ratio from reduced set R calibrated to the actual stress period |
| 9 | **Stress window search** | Full-set plain historical simulation, fallback to Lehman 2008 | MAR33.5(2): reduced set R required; must maximise `ES_R,S` over ≥ 10-year horizon |
| 10 | **NMRF identification** | Single hardcoded flag (`USDTRY`), no RFET | MAR31.12 RFET: ≥ 24 verifiable prices per year, max 30-day gap; MAR33.16–18 category split |
| 11 | **RFET** | Entirely absent — MRF/NMRF split is hardcoded in config | MAR31.12: must be run on live market data; drives SES bucketing |
| 12 | **Backtesting counters** | `max(APL, HPL)` for both desk and bank-wide exception counts | MAR32.5 (bank-wide): 99% HPL only; MAR32.18 (desk): separate APL and HPL counters |
| 13 | **BT / PLAT data** | Gaussian mock P&L (`np.random.normal`) | Production: front-office APL, frozen-portfolio HPL (risk-factor revaluation), risk-engine RTPL |
| 14 | **SA-DRC ratings** | Collapsed to IG / HY / D / NR (worst-case bucket) | MAR22.24 Table 2: per-rating-notch risk weights |
| 15 | **Option JtD** | Set to 0 per MAR22.14 (formally correct) | Some banks apply delta-equivalent hedge recognition in practice |
| 16 | **Vega risk** | Flat vol surface shock per bucket, no term-structure | MAR21 vega: sensitivities per option maturity × underlying tenor grid |
| 17 | **SA-DRC LGD** | Fixed at 100% for equity and 75% for senior debt | MAR22.18: seniority-based LGD schedule, issuer-specific recovery |
| 18 | **Test suite** | 19 unit tests (MAR21 correlation + curvature + stress/edge cases) | SR 11-7 / MAR10.8: full model risk management, benchmark reconciliation, independent validation |
| 19 | **PLA diagnostics** | Aggregate Spearman + KS only | Greek-level delta/vega P&L explain, unexplained-P&L attribution report |
| 20 | **ES horizons** | Single 10-day horizon, no per-risk-class liquidity horizon scaling for MRF | MAR33.12: five liquidity horizon buckets (10/20/40/60/120 days), partial-period extrapolation |
 
---
 
## 🗺️ Minimum Viable Production Roadmap
 
- [ ] Add GIRR, CSR non-sec, Commodity to SBM
- [ ] Replace hardcoded correlations with full MAR21 ρ_kl / γ_bc lookup tables
- [ ] Wire real APL / HPL / RTPL into BT and PLAT modules
- [ ] Implement reduced set R and MAR33.5(2)–33.6 ES ratio correctly
- [ ] Per-ticker MLE GARCH fit + live RFET pipeline
- [ ] IMA-DRC: multi-factor Gaussian copula, real ρ calibration, `N_SIM ≥ 1e6`
- [ ] Index look-through for equity (MAR22.5)
- [ ] Liquidity horizon bucketing for IMA ES (MAR33.12)
- [ ] Real data pipeline with validation and hard-fail on missing data
- [ ] Full test suite + regulatory benchmark reconciliation
- [ ] Model documentation per SR 11-7: data lineage, assumptions, limits, validation
 
---
 
##  Current State
 
> End-to-end FRTB architecture demo with correct SBM aggregation, Vasicek DRC, and FHS-GARCH ES — but **mocked BT/PLAT data**, **incomplete risk class coverage**, and **deliberately flat calibrations**. Suitable as a learning reference or interview demonstration — not for regulatory submission.
