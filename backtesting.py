"""
backtesting.py — VaR backtesting (MAR32).

Desk-level (MAR32.16-32.19): green/red, brak mnożnika, decyzja IMA/SA.
Bank-wide  (MAR32.4-32.15):  green/amber/red, mnożnik m do MAR33.41.
"""
from dataclasses import dataclass
from typing import Literal

import numpy as np

from config import (
    BT_DESK_RED_99, BT_DESK_RED_975, BT_WINDOW,
    BT_MULTIPLIER, BT_MULTIPLIER_RED,
)


# ============================================================================
# Result dataclasses
# ============================================================================
@dataclass
class DeskBacktestResult:
    """Desk-level backtesting (MAR32.16-32.19)."""
    desk_id:        str
    exceptions_99:  int
    exceptions_975: int
    status:         Literal['green', 'red']  # MAR32.19 — brak amber
    ima_eligible:   bool                     # MAR32.19
    n_observations: int


@dataclass
class BankwideBacktestResult:
    """Bank-wide backtesting (MAR32.4-32.15)."""
    exceptions:     int
    status:         Literal['green', 'amber', 'red']  # MAR32.8
    multiplier:     float                             # MAR32.9 Table 1
    n_observations: int


# ============================================================================
# Desk-level runner (MAR32.16-32.19)
# ============================================================================
def run_backtest_desk(
    desk_id: str,
    var_99:  np.ndarray,
    var_975: np.ndarray,
    apl:     np.ndarray,
    hpl:     np.ndarray,
    verbose: bool = True,
) -> DeskBacktestResult:

    for name, arr in {'var_99': var_99, 'var_975': var_975,
                      'apl': apl, 'hpl': hpl}.items():
        if len(arr) != BT_WINDOW:
            raise ValueError(f"{name}: wymagane {BT_WINDOW}, otrzymano {len(arr)}")

    # MAR32.18(1) — exception gdy strata > VaR, max(APL, HPL)
    exceptions_99  = max(int(np.sum(-apl > var_99)),  int(np.sum(-hpl > var_99)))
    exceptions_975 = max(int(np.sum(-apl > var_975)), int(np.sum(-hpl > var_975)))

    # MAR32.19 — tylko red/green
    is_red = (exceptions_99 > BT_DESK_RED_99) or (exceptions_975 > BT_DESK_RED_975)

    result = DeskBacktestResult(
        desk_id        = desk_id,
        exceptions_99  = exceptions_99,
        exceptions_975 = exceptions_975,
        status         = 'red' if is_red else 'green',
        ima_eligible   = not is_red,
        n_observations = BT_WINDOW,
    )
    if verbose:
        _print_desk(result)
    return result


# ============================================================================
# Bank-wide runner (MAR32.4-32.15)
# ============================================================================
def run_backtest_bankwide(
    var_99: np.ndarray,
    apl:    np.ndarray,
    hpl:    np.ndarray,
    verbose: bool = True,
) -> BankwideBacktestResult:

    for name, arr in {'var_99': var_99, 'apl': apl, 'hpl': hpl}.items():
        if len(arr) != BT_WINDOW:
            raise ValueError(f"{name}: wymagane {BT_WINDOW}, otrzymano {len(arr)}")

    # MAR32.5(1) — tylko 99%, max(APL, HPL)
    exceptions = max(int(np.sum(-apl > var_99)), int(np.sum(-hpl > var_99)))

    # MAR32.9 Table 1
    if exceptions >= 10:
        status, multiplier = 'red',   BT_MULTIPLIER_RED
    elif exceptions >= 5:
        status, multiplier = 'amber', BT_MULTIPLIER[exceptions]
    else:
        status, multiplier = 'green', BT_MULTIPLIER[exceptions]

    result = BankwideBacktestResult(
        exceptions     = exceptions,
        status         = status,
        multiplier     = multiplier,
        n_observations = BT_WINDOW,
    )
    if verbose:
        _print_bankwide(result)
    return result


# ============================================================================
# Mock data (DEV ONLY)
# ============================================================================
def generate_mock_var(
    desk_id:  str,
    n:        int = BT_WINDOW,
    seed:     int = 42,
    scenario: Literal['green', 'amber', 'red'] = 'green',
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng     = np.random.default_rng(seed + hash(desk_id) % 1000)
    var_99  = np.abs(rng.normal(1.0, 0.2, size=n))
    var_975 = var_99 * 0.80

    if scenario == 'green':
        apl = rng.normal(0.3, 0.4, size=n)
    elif scenario == 'amber':
        apl = rng.normal(0.0, 1.1, size=n)
    else:
        apl = rng.normal(-0.5, 2.5, size=n)

    hpl = apl + rng.normal(0, 0.1, size=n)
    return var_99, var_975, apl, hpl


# ============================================================================
# Display
# ============================================================================
_ICON = {'green': '[GREEN]', 'amber': '[AMBER]', 'red': '[RED]'}


def _print_desk(r: DeskBacktestResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"Backtesting (desk) — {r.desk_id}   {_ICON[r.status]}")
    print(f"{'=' * 60}")
    print(f"  Observations    : {r.n_observations}")
    print(f"  Exceptions 99%  : {r.exceptions_99:<4}  (red>{BT_DESK_RED_99})")   # MAR32.19
    print(f"  Exceptions 97.5%: {r.exceptions_975:<4}  (red>{BT_DESK_RED_975})") # MAR32.19
    print(f"  IMA eligible    : {'YES' if r.ima_eligible else 'NO (forced SA)'}")
    print(f"{'=' * 60}")


def _print_bankwide(r: BankwideBacktestResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"Backtesting (bank-wide)   {_ICON[r.status]}")
    print(f"{'=' * 60}")
    print(f"  Observations : {r.n_observations}")
    print(f"  Exceptions   : {r.exceptions:<4}  "
          f"(amber>=5, red>=10)")                      # MAR32.9 Table 1
    print(f"  Multiplier   : {r.multiplier:.2f}")      # MAR32.9 Table 1
    print(f"{'=' * 60}")