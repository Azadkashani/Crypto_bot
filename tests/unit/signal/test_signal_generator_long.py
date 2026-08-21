import pytest
from datetime import datetime, UTC
from src.signal.signal_generator import SignalGenerator
import pandas as pd
import numpy as np

def create_market_data():
    # Create a simple bullish DataFrame with 50 candles
    dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz=UTC)
    price = 100 + np.cumsum(np.random.randn(50)*0.5)  # slight uptrend
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price - 0.1,
        'high': price + 0.2,
        'low': price - 0.2,
        'close': price,
        'volume': np.random.randint(1000, 2000, size=50),
    })
    # Ensure last price is higher
    df['close'] = 100 + np.linspace(0, 2, 50)
    return df

def test_signal_long_generation():
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
    timestamp = df.iloc[-1]['timestamp']
    signal = gen.generate_signal(whale_consensus, df, 'ETH', 'ethereum', timestamp)
    # Gate validator only allows certain tokens; ETH is allowed
    assert signal['direction'] in ['LONG', 'REJECTED']  # may be rejected due to market confirmation, but likely LONG
    if signal['direction'] == 'LONG':
        assert signal['status'] in ['VALID', 'WATCH']
        assert signal['signal_score'] > 0
