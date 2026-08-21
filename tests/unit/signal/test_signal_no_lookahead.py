import pytest
from datetime import datetime, timedelta, UTC
from src.signal.signal_generator import SignalGenerator
import pandas as pd

def create_market_data():
    dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz=UTC)
    price = 100.0
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price,
        'high': price,
        'low': price,
        'close': price,
        'volume': 1000.0,
    })
    return df

def test_no_lookahead():
    gen = SignalGenerator()
    whale_consensus = {
        'consensus_score': 90,
        'confidence': 90,
        'direction': 'BULLISH',
        'average_smart_money_score': 85,
        'net_whale_flow': 1000000,
        'independent_buying_whales': 3,
        'independent_selling_whales': 0,
        'data_quality_score': 95,
    }
    df = create_market_data()
    last_ts = df.iloc[-1]['timestamp']
    # Create a future candle after last_ts
    future_row = pd.DataFrame({
        'timestamp': [last_ts + pd.Timedelta(hours=1)],
        'open': [110.0],
        'high': [110.0],
        'low': [110.0],
        'close': [110.0],
        'volume': [5000.0],
    })
    df_with_future = pd.concat([df, future_row], ignore_index=True)
    # Ensure sorted
    df = df.sort_values('timestamp').reset_index(drop=True)
    df_with_future = df_with_future.sort_values('timestamp').reset_index(drop=True)

    signal_no_future = gen.generate_signal(whale_consensus, df, 'ETH', 'ethereum', last_ts)
    signal_with_future = gen.generate_signal(whale_consensus, df_with_future, 'ETH', 'ethereum', last_ts)

    assert signal_no_future['signal_score'] == signal_with_future['signal_score']
    assert signal_no_future['confidence'] == signal_with_future['confidence']
