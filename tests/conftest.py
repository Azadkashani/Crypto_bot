import sys
from pathlib import Path

# افزودن پوشهٔ اصلی پروژه به sys.path تا import ماژول‌ها ممکن شود
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
import pandas as pd
from datetime import datetime, timezone
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
    df['high'] = df[['open','close','high']].max(axis=1)
    df['low'] = df[['open','close','low']].min(axis=1)
    return df

@pytest.fixture
def mock_fetcher(mocker):
    """
    یک DataFetcher که fetch_ohlcv را mock می‌کند.
    """
    fetcher = DataFetcher()
    mocker.patch.object(fetcher, 'fetch_ohlcv', return_value=None)
    return fetcher
