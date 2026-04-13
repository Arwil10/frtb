"""
portfolio/linear.py — linear positions (spot / forwards) as a DataFrame.
"""

import pandas as pd


_LINEAR_DATA = {
    'ID':           [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    'Asset_Class':  ['FX', 'FX', 'FX', 'FX', 'FX', 'Eq', 'Eq', 'Eq', 'Eq', 'Eq'],
    'Desk':         ['FX', 'FX', 'FX', 'FX', 'FX', 'Eq', 'Eq', 'Eq', 'Eq', 'Eq'],
    'Exposure_EUR': [40.0, 15.0, 60.0, 20.0, 35.0, 25.0, 30.0, 20.0, 15.0, 10.0],
    'Type':         ['MRF', 'NMRF', 'MRF', 'MRF', 'MRF', 'MRF', 'MRF', 'MRF', 'MRF', 'MRF'],
    'Ticker':       ['USDPLN=X', 'USDTRY=X', 'EURPLN=X', 'GBPPLN=X', 'JPYPLN=X',
                     '^GSPC', '^GDAXI', '^FTSE', '^N225', 'EEM'],
    'Bucket': ['USD/PLN', 'USD/TRY', 'EUR/PLN', 'GBP/PLN', 'JPY/PLN', 'B12', 'B12', 'B12', 'B12', 'B13'],
    'LH':           [20, 20, 20, 20, 20, 10, 10, 10, 10, 20],
}

LINEAR_DF = pd.DataFrame(_LINEAR_DATA)
