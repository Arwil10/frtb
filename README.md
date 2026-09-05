# Basel IV / FRTB Capital Engine (SA-TB + IMA)

A market risk capital engine implementing FRTB (BCBS d457 / CRR3), running the standardised approach (SA-TB) and internal models approach (IMA) side by side with the 72.5% output floor.

**Disclaimer:** this is an educational prototype, not regulatory-compliant capital calculation software. Simplifications and where they diverge from the standard are listed at the bottom.

## What's in here

1. **SA-TB** — sensitivity-based method (delta, vega, curvature) plus SA-DRC
2. **IMA** — Expected Shortfall via Filtered Historical Simulation with GARCH(1,1), an NMRF stressed add-on, and IMA-DRC through a Vasicek one-factor Monte Carlo
3. **Backtesting (MAR32)** — desk-level and bank-wide, producing the regulatory multiplier m
4. **P&L attribution test (MAR32.34–44)** — Spearman rho and KS statistic on HPL vs RTPL
5. **Output floor (CRR3)** — max(IMA_aggregate, 72.5% × sum of SA)
6. A capital cliff report showing per-desk IMA eligibility and the resulting capital charge

## Layout
