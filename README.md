
### Basel IV / FRTB — Capital Engine (SA-TB + IMA)

# Educational prototype of an FRTB (BCBS d457 / CRR3) market risk capital engine
# Runs SA-TB and IMA in parallel with 72.5% output floor

### 📚 Table of Contents
Overview
Pipeline
Repository Structure
Run
Known Simplifications
Production Roadmap
Current State
Overview
SA-TB — Sensitivity-Based Method
Delta
Vega
Curvature
SA-DRC
IMA — Internal Models Approach
Expected Shortfall (FHS)
GARCH(1,1) volatility filter
NMRF stressed add-on
IMA-DRC via Vasicek Monte Carlo (99.9%, 1Y)
Validation Layer
Backtesting (MAR32) → desk + bank-wide → multiplier m
PLA Test (MAR32.34–44) → Spearman + KS (HPL vs RTPL)
Capital Constraint

Output floor:

72.5% × Σ SA
Pipeline (main.py)
bank-wide BT → multiplier m
→ per-desk IMA + SA
→ desk BT + PLAT
→ IMA eligibility (must pass both)
→ aggregation
→ output floor
→ capital cliff report
Repository Structure
<details> <summary>📂 Expand structure</summary>
main.py
    pipeline runner + final report

config.py
    single source of truth (RWs, correlations, thresholds)

backtesting.py
    MAR32 — desk & bank-wide

plat.py
    MAR32.34–44 — Spearman / KS

pricing/
    black_scholes.py
        BS / Garman-Kohlhagen + analytical greeks

portfolio/
    linear.py
        FX + equity linear positions
    options.py
        FX + equity options
    drc.py
        DRCPosition + hardcoded DRC book
    desks.py
        desk aggregation (FX, Eq)

sa/
    _aggregation.py
        SBM primitives
    delta.py
        §55, §58–60
    vega.py
        §96, §99, §105
    curvature.py
        §108, §121–122
    drc.py
        SA-DRC
    engine.py
        SA runner

ima/
    es.py
        FHS + GARCH + stress window
    drcima.py
        Vasicek MC (99.9%, 1Y)
    engine.py
        IMA runner
</details>
Run
pip install numpy pandas scipy yfinance
python main.py
⚠️ Known Simplifications

[!WARNING]
This is a teaching prototype, not production-grade FRTB implementation.
Deviations from BCBS d457 / CRR3 are intentional.

1. Limited Risk Class Coverage
Only:
FX
Equity
Missing: GIRR, CSR, Commodity, CTP
2. Flat Correlations (DO NAPRAWY)
same = 0.25
cross = 0.15
Used globally across equity buckets
❌ Should use full MAR21 ρ_kl and γ_bc
3. Sovereign Proxy PD (IMA-DRC)
PD derived from country rating
❌ Violates MAR33.24 (needs obligor-level PD)
4. No Equity Index Look-Through
^GSPC treated as single obligor
❌ MAR22.5 requires decomposition
5. Single-Factor Vasicek
One global factor Z
Flat correlation per bucket

[!CAUTION]
Understates concentration risk

6. Low Monte Carlo Resolution
DRC_N_SIM = 100_000
Only ~100 tail observations
❌ Production: 1M–10M+
7. Hardcoded GARCH(1,1)
ω = 1e-6
α = 0.10
β = 0.85
Same parameters for all assets
❌ No MLE calibration
8. Stressed ES Disabled
es_rc = es_curr
ratio = max(es_curr / es_rc, 1.0)
Always ratio = 1
❌ Stress scaling not applied
9. Stress Window Shortcut
Full dataset + pure HS
❌ No reduced set (MAR33.5)
10. Minimal NMRF
Only flag-based
No RFET / categorisation / aggregation rules
11. No RFET (MAR31.12)
Modellability hardcoded
❌ No real price checks
12. Backtesting Simplification

Uses:

max(APL, HPL)

[!IMPORTANT]
Hides diagnostic divergence required by MAR32

13. Mock Data Everywhere
VaR, APL, HPL, RTPL all simulated
Driven by Gaussian generators
14. Simplified SA-DRC
IG / HY buckets only
❌ No rating granularity
15. Equity Options JtD = 0
Formally correct
❌ No hedge recognition
16. Hardcoded Portfolio
2 desks: FX, Eq
No file loader
Tiny dataset
17. Silent Data Fallback
yfinance → synthetic data (no warning)

[!CAUTION]
Critical issue for real capital systems

18. No Tests
No tests/
No validation / reconciliation
19. Repo Hygiene Issues
.Rhistory, .secrets.baseline
Mixed PL/EN comments
Temporary artifacts
20. No PLA Diagnostics
Only aggregate:
Spearman
KS
❌ Missing:
delta explain
vega explain
unexplained P&L
🚧 Minimum Viable Production Roadmap
Core Model Enhancements
Add:
GIRR
CSR non-sec
Commodity
Full MAR21 correlation matrices
IMA Improvements
Reduced set + stress scaling
Per-ticker GARCH (MLE)
RFET implementation
IMA-DRC Upgrade
Multi-factor model
Real correlation calibration
≥ 1M simulations
Data Layer
Real:
APL
HPL
RTPL
Loader + validation + hard-fail
Portfolio Realism
Index look-through
Large-scale book support
Engineering & Governance
Test suite
Benchmark reconciliation
Model documentation (SR 11-7)
📊 Current State

[!NOTE]
This project demonstrates end-to-end FRTB architecture

✅ What’s correct
SBM structure
Vasicek formulation
Pipeline logic (SA vs IMA + eligibility + floor)
❌ What’s missing
Real data
Full risk coverage
Proper calibration
Regulatory completeness
