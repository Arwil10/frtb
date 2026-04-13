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
