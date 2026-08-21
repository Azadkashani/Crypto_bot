import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
import numpy as np
from src.research.backtester import Backtester
from src.research.metrics import compute_basic_stats

def create_price_data():
    # Generate 1h candles for 48 hours
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(49)]
    price = 100.0
    rows = []
    for ts in dates:
        open_price = price
        high = price * 1.02
        low = price * 0.98
        close = price * 1.01  # uptrend
        rows.append({'timestamp': ts, 'open': open_price, 'high': high, 'low': low, 'close': close})
        price = close
    df = pd.DataFrame(rows)
    return {'TOKEN': df}

def create_signals():
    start = datetime(2024,1,1,tzinfo=UTC)
    signals = []
    for i in range(0, 24, 2):  # every 2 hours
        ts = start + timedelta(hours=i)
        signals.append({
            'token': 'TOKEN',
            'chain': 'ethereum',
            'timestamp': ts,
            'direction': 'LONG',
            'signal_score': 80,
            'confidence': 80,
        })
    return signals

def test_backtest_runs():
    price_data = create_price_data()
    signals = create_signals()
    bt = Backtester(price_data, signals)
    results = bt.run()
    assert len(results) > 0
    stats = compute_basic_stats(results)
    assert stats['sample_size'] > 0
