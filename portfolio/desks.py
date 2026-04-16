"""
portfolio/desks.py — Desk aggregation (linear + options, grouped per desk).
"""

from dataclasses import dataclass, field
import pandas as pd

from pricing.black_scholes import BSOption
from portfolio.linear  import LINEAR_DF
from portfolio.options import OPTIONS


@dataclass
class Desk:
    desk_id:   str
    positions: pd.DataFrame
    options:   list[BSOption] = field(default_factory=list)


DESKS: dict[str, Desk] = {
    'FX': Desk(
        desk_id   = 'FX',
        positions = LINEAR_DF[LINEAR_DF['Desk'] == 'FX'].reset_index(drop=True),
        options   = [o for o in OPTIONS if o.asset_class == 'FX'],
    ),
    'Eq': Desk(
        desk_id   = 'Eq',
        positions = LINEAR_DF[LINEAR_DF['Desk'] == 'Eq'].reset_index(drop=True),
        options   = [o for o in OPTIONS if o.asset_class == 'Eq'],
    ),
}
