import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.backtester import Backtester

def test_no_lookahead_future_candles():
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(24)]
    price = 100.0
    rows = []
    for ts in dates:
        rows.append({'timestamp': ts, 'open': price, 'high': price*1.01, 'low': price*0.99, 'close': price*1.005})
        price = price*1.005
    df_before = pd.DataFrame(rows)
    # Add future candles after the last signal timestamp (signal at hour 10)
    last_signal_time = start + timedelta(hours=10)
    future_dates = [start + timedelta(hours=i) for i in range(24, 30)]
    future_rows = []
    for ts in future_dates:
        future_rows.append({'timestamp': ts, 'open': 200, 'high': 200, 'low': 200, 'close': 200})
    df_after = pd.concat([df_before, pd.DataFrame(future_rows)], ignore_index=True)
    df_after = df_after.sort_values('timestamp').reset_index(drop=True)
    signals = [{'token': 'TOKEN', 'chain': 'ethereum', 'timestamp': last_signal_time, 'direction': 'LONG', 'signal_score': 80, 'confidence': 80}]
    price_data_before = {'TOKEN': df_before}
    price_data_after = {'TOKEN': df_after}
    bt1 = Backtester(price_data_before, signals)
    bt2 = Backtester(price_data_after, signals)
    res1 = bt1.run()
    res2 = bt2.run()
    # Since signals are same and past data same, results should be identical
    assert len(res1) == len(res2)
    for r1, r2 in zip(res1, res2):
        assert r1['return_pct'] == r2['return_pct']
        assert r1['entry_price'] == r2['entry_price']
