import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.baselines import random_baseline

def test_random_baseline():
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(24)]
    rows = []
    for ts in dates:
        rows.append({'timestamp': ts, 'open': 100, 'high': 102, 'low': 98, 'close': 101})
    df = pd.DataFrame(rows)
    price_data = {'TOKEN': df}
    signals = [{'token': 'TOKEN', 'chain': 'ethereum', 'timestamp': start + timedelta(hours=5), 'direction': 'LONG', 'signal_score': 80, 'confidence': 80}]
    res = random_baseline(signals, price_data, iterations=10)
    assert 'avg_win_rate' in res
    assert res['iterations'] == 10
