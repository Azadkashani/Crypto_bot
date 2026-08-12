import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from data import DataFetcher

@pytest.fixture
def sample_ohlcv_data():
    """
    داده OHLCV مصنوعی برای تست (30 کندل 5m).
    """
    now = datetime.now(timezone.utc)
    index = pd.date_range(end=now, periods=30, freq='5min', tz='UTC')
    import numpy as np
    np.random.seed(42)
    df = pd.DataFrame({
        'open': np.random.randn(30).cumsum() + 50000,
        'high': np.random.randn(30).cumsum() + 50100,
        'low': np.random.randn(30).cumsum() + 49900,
        'close': np.random.randn(30).cumsum() + 50000,
        'volume': np.random.randint(100, 1000, 30)
    }, index=index)
    # اطمینان از high >= low, open/close inside range
    df['high'] = df[['open','close','high']].max(axis=1)
    df['low'] = df[['open','close','low']].min(axis=1)
    return df

@pytest.fixture
def mock_fetcher(mocker):
    """
    یک DataFetcher که fetch_ohlcv را mock می‌کند تا از اینترنت بی‌نیاز باشیم.
    """
    fetcher = DataFetcher()
    mocker.patch.object(fetcher, 'fetch_ohlcv', return_value=None)
    return fetcher
