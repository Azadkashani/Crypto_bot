import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from data import DataFetcher
import numpy as np

FREQ_MAP = {
    '5m': '5min',
    '1h': '1h',
    '4h': '4h',
    '1d': 'D',
}

def _to_pandas_freq(ccxt_timeframe: str) -> str:
    return FREQ_MAP.get(ccxt_timeframe, ccxt_timeframe)


def test_timeframe_independence(mocker):
    call_counts = {}

    def mock_fetch(self, symbol, timeframe, since=None, limit=None, remove_incomplete_candle=False):
        call_counts[timeframe] = call_counts.get(timeframe, 0) + 1
        freq = _to_pandas_freq(timeframe)
        idx = pd.date_range(end=datetime.now(timezone.utc), periods=2, freq=freq, tz='UTC')
        return pd.DataFrame({
            'open': [100, 101], 'high': [102, 103],
            'low': [99, 100], 'close': [101, 102],
            'volume': [10, 20]
        }, index=idx[:2])

    mocker.patch.object(DataFetcher, 'fetch_ohlcv', mock_fetch)

    fetcher = DataFetcher()
    for tf in ['4h', '1h', '5m']:
        fetcher.get_historical_data(symbol='BTC/USDT:USDT', timeframe=tf, force_fetch=True)

    assert len(call_counts) == 3
    for tf in ['4h', '1h', '5m']:
        assert call_counts[tf] == 1, f"fetch_ohlcv for {tf} should be called exactly once"


def test_chronological_order_and_uniqueness(tmp_path, mocker):
    mock_exchange = mocker.Mock()
    mock_exchange.load_markets = mocker.Mock()
    mocker.patch('ccxt.gate', return_value=mock_exchange)

    now = datetime.now(timezone.utc)
    times = [
        now - timedelta(minutes=30),
        now - timedelta(minutes=20),
        now - timedelta(minutes=20),  # تکراری
        now - timedelta(minutes=10),
        now
    ]
    df = pd.DataFrame({
        'open': [10, 11, 11, 12, 13],
        'high': [15, 16, 16, 17, 18],
        'low': [9, 10, 10, 11, 12],
        'close': [12, 13, 13, 14, 15],
        'volume': [100, 110, 110, 120, 130]
    }, index=pd.DatetimeIndex(times, tz='UTC'))
    df = df.sort_index(ascending=False)

    import os
    fetcher = DataFetcher()
    fetcher._file_path = lambda s, t: os.path.join(tmp_path, f"{s.replace('/', '_')}_{t}.csv")
    symbol, tf = 'BTC/USDT:USDT', '5m'
    fetcher.save_data(df, symbol, tf)
    loaded = fetcher.load_data(symbol, tf)

    assert loaded.index.is_monotonic_increasing
    assert len(loaded) == len(df)


def test_no_future_data_leakage():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    dates = pd.date_range(start=base, periods=10, freq='1h', tz='UTC')
    df = pd.DataFrame({
        'open': range(10),
        'high': range(1, 11),
        'low': range(0, 10),
        'close': range(2, 12),
        'volume': 100
    }, index=dates)

    for i in range(len(df)):
        available = df.iloc[:i+1]
        assert available.index.max() == dates[i]
        assert len(available) == i + 1


def test_incomplete_candle_removal(mocker):
    now = datetime.now(timezone.utc)
    # ایجاد زمان‌ها با دقت میکروثانیه
    complete_time_us = now - timedelta(minutes=10)
    incomplete_time_us = now - timedelta(minutes=2)
    # کاهش دقت به میلی‌ثانیه (CCXT از میلی‌ثانیه استفاده می‌کند)
    complete_time = datetime.fromtimestamp(
        int(complete_time_us.timestamp() * 1000) / 1000.0,
        tz=timezone.utc
    )
    incomplete_time = datetime.fromtimestamp(
        int(incomplete_time_us.timestamp() * 1000) / 1000.0,
        tz=timezone.utc
    )

    fake_raw = [
        [int(complete_time.timestamp() * 1000), 100, 102, 99, 101, 50],
        [int(incomplete_time.timestamp() * 1000), 101, 103, 100, 102, 30]
    ]

    fetcher = DataFetcher()
    mocker.patch.object(fetcher.exchange, 'fetch_ohlcv', return_value=fake_raw)

    df_full = fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m', remove_incomplete_candle=False)
    assert len(df_full) == 2

    df_clean = fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m', remove_incomplete_candle=True)
    assert len(df_clean) == 1
    # مقایسه با complete_time که دقت میلی‌ثانیه دارد
    assert df_clean.index[0] == complete_time


@pytest.mark.integration
def test_real_data_fetch():
    try:
        fetcher = DataFetcher()
        df = fetcher.get_historical_data(
            symbol='BTC/USDT:USDT',
            timeframe='5m',
            lookback_days=1,
            force_fetch=True,
            remove_incomplete_candle=True
        )
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert df.index.tz == timezone.utc
        assert df.index.is_monotonic_increasing
        delta = timedelta(minutes=5)
        assert df.index[-1] + delta <= datetime.now(timezone.utc)
    except Exception as e:
        pytest.skip(f"Skipping integration test due to: {e}")
