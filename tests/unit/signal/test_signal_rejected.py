import pytest
from datetime import datetime, UTC
from src.signal.signal_generator import SignalGenerator
import pandas as pd

def create_market_data():
    dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz=UTC)
    price = 100
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price,
        'high': price,
        'low': price,
        'close': price,
        'volume': 1000,
    })
    return df

def test_signal_rejected_low_consensus():
    gen = SignalGenerator()
    whale_consensus = {
        'consensus_score': 40,
        'confidence': 50,
        'direction': 'BULLISH',
        'average_smart_money_score': 50,
        'net_whale_flow': 0,
        'independent_buying_whales': 1,
        'independent_selling_whales': 0,
        'data_quality_score': 50,
    }
    df = create_market_data()
    timestamp = df.iloc[-1]['timestamp']
    signal = gen.generate_signal(whale_consensus, df, 'TOKENX', 'ethereum', timestamp)
    # Either REJECTED or INSUFFICIENT_DATA
    assert signal['direction'] in ['REJECTED', 'NEUTRAL']
