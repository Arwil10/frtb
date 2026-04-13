# Basel IV / FRTB — Capital Engine (SA-TB + IMA)

Educational prototype of an **FRTB** (BCBS d457 / CRR3) market risk capital
engine. Runs both approaches in parallel and applies the **72.5% output floor**:

- **SA-TB** — Sensitivity-Based Method (delta, vega, curvature) + SA-DRC
- **IMA** — Expected Shortfall via Filtered Historical Simulation with
  GARCH(1,1) filter, NMRF stressed add-on, IMA-DRC via Vasicek one-factor MC
- **Backtesting** (MAR32) — desk-level and bank-wide (→ multiplier *m*)
- **PLA Test** (MAR32.34–44) — Spearman + KS on HPL vs RTPL
- **Output floor** (CRR3 art. 89) — 72.5% × Σ SA

Pipeline in `main.py`: bank-wide BT → *m* → per-desk IMA and SA → desk BT +
PLAT → desk is IMA-eligible only if both pass → aggregate + floor + capital
cliff report.

## Repo layout

```
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
```

## Run

```bash
pip install numpy pandas scipy yfinance
python main.py
```

---

# ⚠️ Known simplifications

This is a teaching prototype, **not production-grade**. Each item below is a
deliberate shortcut and a gap vs. d457 / CRR3.

### 1. Only 2 of 7 SBM risk classes

FX and Equity only. **GIRR, CSR non-sec, CSR sec, CTP, Commodity** are
missing entirely — and GIRR/CSR are usually the largest SA-TB contributors at
real banks.

### 2. `CORR_SCENARIOS` are flat and marked `DO NAPRAWY` in the code

`config.py` uses a single `(same=0.25, cross=0.15)` pair for all equity
buckets. MAR21.78/80 requires per-bucket ρ_kl and per-pair γ_bc tables. The
low-correlation scenario formula is correct (MAR21.6(3)), but the base ρ is
wrong.

### 3. IMA-DRC uses sovereign PD proxy

`IMA_DRC_PD_INTERNAL` assigns PDs based on the **sovereign rating** of the
index issuer's country (comment in code: *"UŻYTO METODY SOVEREIGN PROXY"*).
MAR33.24 requires obligor-level PDs from IRB models or market data. Equity
indices are not sovereign bonds.

### 4. No look-through for equity indices (MAR22.5)

`portfolio/drc.py` treats `^GSPC` as one position. MAR22.5 requires decomposing
indices into single-name components for JtD. For a 500-name index this
distortion is severe.

### 5. Single-factor Vasicek for IMA-DRC

One global factor `Z` for all obligors, flat ρ per bucket
(IG=0.75 / HY=0.50 / EM=0.20). Real banks use multi-factor models calibrated
from historical co-defaults or equity correlations. Single-factor dramatically
understates concentration risk.

### 6. `DRC_N_SIM = 100_000` is too low for 99.9%

Only ~100 observations in the tail. The in-code comment admits *"minimum
viable due to computational constraints"*. Production uses 1–10M sims, often
with importance sampling.

### 7. GARCH(1,1) parameters hardcoded, no MLE

ω=1e-6, α=0.10, β=0.85 applied to every risk factor — S&P and USDTRY share
the same variance process. Real FHS fits GARCH per ticker via MLE.

### 8. Stressed ES: no reduced set (MAR33.5(2))

In `compute_stressed_es`:

```python
es_rc = es_curr   # placeholder — no reduced set
ratio = max(es_curr / es_rc, 1.0)   # always 1.0
```

The entire stress-calibration scaling factor is effectively disabled.
`es_applied` collapses to just `es_stressed`.

### 9. `find_stress_window` uses pure HS on the full set

MAR33.5(2) requires a reduced set for the stress window search; the code
scans ~20 years on the full set with pure HS (to avoid GARCH σ_current
artifacts). Pragmatic compromise, not compliant. The fallback silently
returns the Lehman window if data is missing.

### 10. NMRF treatment is minimal

NMRF is just a `Type == 'NMRF'` flag in the DataFrame, with one position
(`USDTRY=X`). No RFET, no category split (idiosyncratic credit vs. equity
vs. other), no aggregation rules from MAR33.16–33.18.

### 11. No Risk Factor Eligibility Test (MAR31.12)

No modellability check (24+ real prices in 12 months, max 30-day gap). The
MRF/NMRF split is hardcoded in `portfolio/linear.py`.

### 12. Backtesting takes `max(APL, HPL)` exceptions

Conservative but hides HPL-vs-APL divergence, which is the diagnostic signal
for model quality. MAR32.5/32.18 expect both counters reported separately.

### 13. All BT and PLAT run on mock data

`generate_mock_var` and `generate_mock_pnl` generate VaR/APL/HPL/RTPL from
gaussians controlled by `scenario ∈ {green, amber, red}`. **The bank's
multiplier *m* and every desk's IMA-eligibility are driven by flags in
`main.py`, not historical P&L.** Production needs front-office APL,
frozen-portfolio HPL, and risk-engine RTPL.

### 14. `SA_DRC_RW_BUCKET` collapses ratings to IG/HY/D/NR

`sa/drc.py` uses the bucketed version with worst-case weights (BBB for IG,
CCC for HY) instead of the per-rating MAR22.24 Table 2 (`SA_DRC_RW_NON_SEC`
exists in config but is unused).

### 15. Equity option JtD = 0

Formally correct per MAR22.14(1)(c) — option expires, no jump — but it means
option hedges contribute nothing to DRC in either SA or IMA. Most banks apply
delta-equivalent approximations for hedge recognition.

### 16. Hardcoded portfolio, two desks

10 linear positions, 6 options, 8 DRC positions, `DESKS = {'FX', 'Eq'}`. No
CSV/Parquet loader. Real books have hundreds of thousands of trades across
dozens of desks.

### 17. yfinance silently falls back to synthetic data

`get_returns` wraps yfinance in a bare `try/except` and on failure returns
`_synthetic_returns(seed=42)` with no warning. For a capital system this is
critical — a rate limit should hard-fail, not replace real data with noise.

### 18. No tests

No `tests/`, no doctests, no reconciliation harness. For regulatory capital
code this is the biggest audit red flag (SR 11-7 / MAR10.8 model risk
management).

### 19. Repo hygiene

- `.Rhistory` and `.secrets.baseline` checked in (empty)
- `repomix-output.md` committed alongside sources
- "DO USUNIĘCIA po migracji" aliases still live in `config.py`
- Comments mix Polish and English
- `plat.py` has two module docstrings in a row
- Commented-out yfinance smoke test at the top of `ima/es.py`

### 20. No per-factor PLA diagnostics

PLAT only computes Spearman + KS on aggregate HPL/RTPL. No greek-level
decomposition (delta-explain, vega-explain), no unexplained-P&L report — all
standard extensions that tell you *why* a desk fails.

---

## Minimum viable production roadmap

1. Add **GIRR, CSR non-sec, Commodity** to SBM.
2. Replace `CORR_SCENARIOS` with full MAR21 ρ_kl / γ_bc tables.
3. Wire real **APL / HPL / RTPL** into BT and PLAT.
4. Implement reduced set + proper MAR33.5(2)–33.6 ratio.
5. Per-ticker MLE GARCH fit + RFET.
6. IMA-DRC: multi-factor model, real ρ calibration, `N_SIM ≥ 1e6`.
7. Look-through for equity indices (MAR22.5).
8. Real data pipeline (loader, validation, hard-fail).
9. Test suite + regulatory benchmark reconciliation.
10. Model documentation (SR 11-7): data, assumptions, limits, validation.

**Current state:** end-to-end FRTB architecture demo with correct SBM and
Vasicek formulas, but mocked data, incomplete risk class coverage, and many
deliberately flat calibrations.
