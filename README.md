# Basel IV / FRTB Capital Engine (SA-TB + IMA)

A market risk capital engine implementing FRTB  running the standardised approach and internal models approach.
**Disclaimer:** this is an educational prototype, simplifications and shortcuts are present.

## What's in here

1. **SA** — sensitivity-based method (delta, vega, curvature) plus SA-DRC
2. **IMA** — Expected Shortfall via Filtered Historical Simulation with GARCH(1,1), an NMRF stressed add-on, IMA-DRC through a Vasicek one-factor Monte Carlo
3. **Backtesting** — desk-level and bank-wide, producing the regulatory multiplier m
4. **P&L attribution test** — Spearman rho and KS statistic on HPL vs RTPL
5. **Output floor** — max(IMA_aggregate, 72.5% × sum of SA)
6. A report showing per-desk IMA eligibility and the resulting capital charge

## Layout

├── main.py # orchestrator — runs the full pipeline
├── config.py # regulatory parameters (risk weights, correlations, liquidity horizons)
├── backtesting.py # MAR32 desk-level and bank-wide VaR backtesting
├── plat.py # MAR32.34–44 P&L attribution test
├── sa/
│ ├── delta.py # delta SBM — FX & equity
│ ├── vega.py # vega SBM — options vol sensitivities
│ ├── curvature.py # curvature risk — BS re-pricing with the psi indicator
│ ├── drc.py # SA-DRC — JtD × LGD × risk weight
│ ├── engine.py # SA-TB orchestrator
│ └── _aggregation.py # SBM bucket / cross-bucket aggregation
├── ima/
│ ├── es.py # FHS-GARCH Expected Shortfall (MAR33)
│ ├── drcima.py # IMA-DRC — Vasicek one-factor MC (MAR33.24)
│ └── engine.py # IMA orchestrator (ES + SES_NMRF + DRC)
├── portfolio/
│ ├── linear.py # linear positions (FX spots, equity)
│ ├── options.py # BSOption dataclass + portfolio
│ ├── desks.py # desk definitions
│ └── drc.py # DRC position dataclass
├── pricing/
│ └── black_scholes.py # Black-Scholes pricer (delta, vega, re-pricing)
└── tests/
├── test_corr_scenarios.py # MAR21.6 correlation scenario ordering
├── test_curvature.py # CVR logic, psi indicator, bucket_K (MAR21.5)
├── test_properties.py # non-negativity and monotonicity
└── test_stress.py # edge cases: empty portfolio, zero sigma, full offset


## Methodology

**Output floor**

$$K = \max\!\left(\text{IMA}_{agg},\; 0.725 \times \sum_{d} \text{SA}_{d}\right)$$

**IMA desk charge**

$$\text{IMA}_{d} = \underbrace{ES_{F,C} \times \frac{ES_{R,S}}{ES_{R,C}} \times m}_{\text{Capital MRF}} + \underbrace{SES_{NMRF}}_{\text{NMRF add-on}} + \underbrace{DRC_{IMA}}_{\text{Vasicek MC}}$$

where $m$ is the backtesting multiplier from MAR32.9 Table 1 (1.5 in the green zone).

**Expected Shortfall — FHS-GARCH (MAR33.3)**

$$ES_{t} = -\frac{1}{T \cdot \alpha} \sum_{\tau: r_\tau < \text{VaR}_\alpha} r_\tau, \qquad \tilde{r}_\tau = \frac{\epsilon_\tau}{\hat{\sigma}_\tau} \cdot \hat{\sigma}_t$$

Returns get standardised by the GARCH(1,1) conditional volatility, then rescaled to the current variance before taking the tail average — that's the filtered historical simulation step.

**GARCH(1,1) variance process**

$$\sigma_t^2 = \omega + \alpha\,\epsilon_{t-1}^2 + \beta\,\sigma_{t-1}^2$$


**IMA-DRC — Vasicek one-factor**

$$L_i = \mathbf{1}\!\left[\sqrt{\rho_i}\,Z + \sqrt{1-\rho_i}\,\epsilon_i \leq \Phi^{-1}(PD_i)\right] \times JtD_i$$


**NMRF stressed add-on**

$$SES_{NMRF} = \sqrt{\sum_{q} SES_q^2}, \qquad SES_q = ES_q^{RS} \times \sqrt{\frac{LH_q}{10}}$$

square-root-of-time scaling by liquidity horizon.

**SA-TB — SBM aggregation (MAR21.4)**

Within a bucket:

$$K_b = \sqrt{\sum_k WS_k^2 + \rho_{kl} \sum_{k \neq l} WS_k \cdot WS_l}$$

Across buckets:

$$\text{SA-TB} = \max\!\left(\sqrt{\sum_b K_b^2 + \gamma_{bc} \sum_{b \neq c} S_b \cdot S_c},\; 0\right)$$

Three correlation scenarios per MAR21.6 (low/medium/high), worst case is taken.

**Curvature CVR (MAR21.5)**

$$CVR_k^{\pm} = -\!\left[\,V(x_k^{\pm}) - V(x_k) \mp RW_k^{curv} \cdot \delta_k\right]$$

$$K_b^{curv} = \sqrt{\max\!\left(\sum_k \max(CVR_k, 0)^2 + \rho_{kl}\sum_{k\neq l}\psi(CVR_k, CVR_l)\cdot CVR_k \cdot CVR_l,\; 0\right)}$$

where $\psi(CVR_k, CVR_l) = 0$ when both are negative, per MAR21.5(3).

## Running it

```bash
pip install numpy pandas scipy yfinance
python main.py
```

## Results on the prototype portfolio (FX + equity desks)

Numbers below are demonstratory from one of the outputs.

### Capital stack

| Component | Desk | Approach | RWA (mln EUR) |
| :--- | :--- | :--- | ---: |
| Delta + vega + curvature (SBM) | FX | SA-TB | included below |
| SA-DRC | FX | SA-TB | 0.00 |
| **SA-TB total** | **FX** | **SA-TB** | **239.43** |
| ES MRF (m = 1.50, stress window Jun 2008 – Jul 2009) | FX | IMA | 68.41 |
| SES NMRF (USDTRY, flagged) | FX | IMA | 7.34 |
| IMA-DRC | FX | IMA | 0.00 |
| **IMA total** | **FX** | **IMA** | **75.74** |
| Delta + vega + curvature (SBM) | Eq | SA-TB | included below |
| SA-DRC | Eq | SA-TB | 2.62 |
| **SA-TB total** | **Eq** | **SA-TB** | **209.41** |
| ES MRF (m = 1.50, stress window Sep 2007 – Dec 2008) | Eq | IMA | 186.57 |
| SES NMRF | Eq | IMA | 0.00 |
| IMA-DRC (Vasicek MC, 1M sims, 99.9%) | Eq | IMA | 187.50 |
| **IMA total** | **Eq** | **IMA** | **374.07** |

### Backtesting and PLA eligibility

| Desk | BT (99%) | BT status | Spearman rho | KS stat | PLAT | Source used | Capital cliff |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | ---: |
| FX | 1 exception | green | 0.105 | 0.292 | fail | SA (PLAT fail) | +163.69 mln EUR |
| Eq | 0 exceptions | green | 0.988 | 0.032 | pass | IMA | 0.00 |

Bank-wide backtest: green, 1 exception over 250 observations, so m = 1.50.

### Final capital

| | RWA (mln EUR) |
| :--- | ---: |
| Portfolio RWA (post BT/PLAT) | **613.49** |
| SA total (both desks) | 448.84 |
| Output floor (72.5% × SA) | 325.41 |
| Floor binding? | No (+288.09 above floor) |
| **RWA final** | **613.49** |
| Capital cliff (FX PLAT failure) | **+163.69 mln EUR (+36.4% vs pure IMA)** |

The FX desk fails the P&L attribution test (Spearman 0.105, KS 0.292), so it falls back from IMA (75.74 mln) to SA (239.43 mln)

## Pipeline flow

portfolio/
linear positions (FX spots, equity)
options (BSOption -> Black-Scholes pricer)
|
+--> SA-TB engine
| delta.py -> SBM (FX + equity buckets)
| vega.py -> SBM (vol surface buckets)
| curvature.py -> CVR re-pricing + psi indicator
| drc.py -> JtD x LGD x weight
|
+--> IMA engine
| es.py -> FHS-GARCH ES, stress window search
| drcima.py -> Vasicek MC, VaR 99.9%
| NMRF flag -> SES add-on
|
+--> Backtesting (MAR32)
| desk-level: green/red -> IMA eligibility
| bank-wide: m multiplier
|
+--> PLAT (MAR32.34-44)
| Spearman rho + KS(HPL, RTPL)
| green/amber/red -> IMA eligibility
|
+--> Capital aggregation
per-desk: IMA or SA (BT+PLAT gating)
bank-wide: max(sum IMA_desk, 72.5% x sum SA_desk)
capital cliff report


## Known simplifications

| # | Area | Simplification | 
| :--- | :--- | :--- | 
| 1 | Risk classes | FX and equity only | 
| 2 | Correlation scenarios | Single flat rho per risk class, hardcoded | 
| 3 | IMA-DRC PDs | Sovereign proxy (IG floor 0.03%, EM 1.0%) applied to all equity index issuers | 
| 4 | Vasicek model | Single-factor, flat rho per rating bucket (IG 0.30, EM 0.15) | 
| 5 | Stressed ES ratio | ES_(R,S) / ES_(R,C) forced to 1.0 |
| 6 | NMRF identification | Single hardcoded flag (USDTRY), no RFET |
| 7 | RFET | Absent entirely — MRF/NMRF split hardcoded in config | 
| 8 | Vega risk | Flat vol surface shock per bucket, no term structure | 
| 9 | Test suite | 19 unit tests (MAR21 correlation, curvature, stress/edge cases) | 
| 10 | PLA diagnostics | Aggregate Spearman + KS only | |

## Roadmap

- Add GIRR, CSR non-sec, commodity to the SBM
- Replace hardcoded correlations with the full MAR21 rho_kl / gamma_bc tables
- Implement the reduced set R and MAR33.5(2)–33.6 ES ratio properly
- Real data pipeline with validation and hard-fail on missing data
- Model documentation per SR 11-7n
