import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.evaluator import compute_mfe_mae

def test_mfe_mae():
    entry_time = datetime(2024,1,1,12,0,tzinfo=UTC)
    entry_price = 100.0
    candles = pd.DataFrame([
        {'timestamp': entry_time + timedelta(hours=1), 'open': 100, 'high': 110, 'low': 95, 'close': 105},
        {'timestamp': entry_time + timedelta(hours=2), 'open': 105, 'high': 115, 'low': 100, 'close': 110},
    ])
    mfe, mae = compute_mfe_mae(candles, entry_time, entry_price, timedelta(hours=2), 'LONG')
    assert mfe == (115 - 100) / 100 * 100
    assert mae == (100 - 95) / 100 * 100
