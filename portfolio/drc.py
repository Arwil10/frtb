"""
portfolio/drcima.py — DRC positions (equity only, LGD=100% per d457 §133).
"""

from dataclasses import dataclass
from typing import Literal

from config import IMA_DRC_PD_INTERNAL as RATING_PD, SA_DRC_RW_NON_SEC, RATING_BUCKET

@dataclass
class DRCPosition:
    pos_id:       int
    desk_id:      str
    obligor_id:   str
    instrument:   Literal['equity', 'equity_option']
    notional_eur: float                 # signed: + long, - short
    rating:       str
    sector:       str = 'index'
    lgd:          float = 1.0           # §133: equity LGD = 100%

    def __post_init__(self):
        self.pd = RATING_PD.get(self.rating, RATING_PD['NR'])

    @property
    def rating_bucket(self) -> str:
        return RATING_BUCKET.get(self.rating, 'NR')

    @property
    def jtd_gross(self) -> float:
        if self.instrument == 'equity_option':
            return 0.0  # MAR22.14(1)(c) — opcja wygasa, JtD=0
        return self.lgd * self.notional_eur if self.notional_eur >= 0 \
            else -abs(self.notional_eur)


# NOTE: equity indices used as proxy for single-name look-through
    # (MAR22.5 requires look-through in production)


DRC_POSITIONS: list[DRCPosition] = [
    # Sovereign proxy ratings — MAR33 equity JtD = price → 0
    # Rating = sovereign rating kraju, nie korporacyjny
    DRCPosition(1, 'Eq', '^GSPC',  'equity', 25.0, 'AA',  'index_dm'),  # USA  AA+  PD≈0.02%
    DRCPosition(2, 'Eq', '^GDAXI', 'equity', 30.0, 'AAA', 'index_dm'),  # DEU  AAA  PD≈0.01%
    DRCPosition(3, 'Eq', '^FTSE',  'equity', 20.0, 'AA',  'index_dm'),  # GBR  AA   PD≈0.02%
    DRCPosition(4, 'Eq', '^N225',  'equity', 15.0, 'A',   'index_dm'),  # JPN  A+   PD≈0.07%
    DRCPosition(5, 'Eq', 'EEM',    'equity', 10.0, 'BB',  'index_em'),  # EM   BB   PD≈1.00%

    # Opcje — JtD=0 per MAR22.14(1)(c)
    DRCPosition(6, 'Eq', '^GSPC',  'equity_option', 30.0, 'AA',  'index_dm'),
    DRCPosition(7, 'Eq', '^GDAXI', 'equity_option', 12.0, 'AAA', 'index_dm'),
    DRCPosition(8, 'Eq', 'EEM',    'equity_option',  8.0, 'BB',  'index_em'),
]


def get_desk_drc_positions(desk_id: str) -> list[DRCPosition]:
    return [p for p in DRC_POSITIONS if p.desk_id == desk_id]
