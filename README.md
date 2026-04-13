## Basel IV / FRTB — Capital Engine (SA-TB + IMA)

Educational prototype of an FRTB (BCBS d457 / CRR3) market risk capital
engine. Runs both approaches in parallel and applies the 72.5% output floor:

- SA-TB — Sensitivity-Based Method (delta, vega, curvature) + SA-DRC
- IMA — Expected Shortfall via Filtered Historical Simulation with
GARCH(1,1) filter, NMRF stressed add-on, IMA-DRC via Vasicek one-factor MC
- Backtesting (MAR32) — desk-level and bank-wide (→ multiplier m)
- PLA Test (MAR32.34–44) — Spearman + KS on HPL vs RTPL
- Output floor (CRR3 art. 89) — 72.5% × Σ SA

Pipeline in main.py: bank-wide BT → m → per-desk IMA and SA → desk BT +
PLAT → desk is IMA-eligible only if both pass → aggregate + floor + capital
cliff report.

# Repo layout
main.py                 pipeline runner + final report
config.py               single source of truth (RWs, correlations, thresholds)
backtesting.py          MAR32 — desk & bank-wide
plat.py                 MAR32.34–44 — Spearman / KS

pricing/black_scholes.py    BS / Garman-Kohlhagen + analytical greeks

portfolio/
  linear.py             spot/forward FX + equity positions
  options.py            FX + equity option book
  drc.py                DRCPosition + hardcoded DRC positions
  desks.py              desk aggregation (FX, Eq)

sa/                     Standardised Approach
  _aggregation.py       SBM primitives
  delta.py              §55, §58–60
  vega.py               §96, §99, §105
  curvature.py          §108, §121–122 (γ² in cross-bucket)
  drc.py                SA-DRC (bucket / pd_based methods)
  engine.py             SA runner

ima/                    Internal Models Approach
  es.py                 FHS + GARCH(1,1), NMRF shock, stress window finder
  drcima.py             IMA-DRC — Vasicek MC, 99.9%, 1Y
  engine.py             IMA runner
