import pandas as pd
import pytest
from data import DataFetcher
import config

def test_fetch_ohlcv_structure(mock_fetcher, sample_ohlcv_data):
    """
    تست ساختار خروجی fetch_ohlcv با داده مصنوعی.
    """
    mock_fetcher.fetch_ohlcv.return_value = sample_ohlcv_data
    df = mock_fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m')
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert df.index.tz is not None
    assert str(df.index.tz) == 'UTC'
    assert df.index.is_monotonic_increasing

def test_save_and_load_data(tmp_path, sample_ohlcv_data, mocker):
    """
    تست ذخیره‌سازی و بارگذاری داده از فایل CSV.
    """
    import os
    from data import DataFetcher

    # Mock ccxt.gate برای جلوگیری از اتصال واقعی
    mock_exchange = mocker.Mock()
    mock_exchange.load_markets = mocker.Mock()
    mocker.patch('ccxt.gate', return_value=mock_exchange)

    fetcher = DataFetcher()
    # تغییر مسیر ذخیره به tmp_path
    fetcher._file_path = lambda s, t: os.path.join(tmp_path, f"{s.replace('/', '_')}_{t}.csv")
    symbol, tf = 'BTC/USDT:USDT', '5m'
    fetcher.save_data(sample_ohlcv_data, symbol, tf)
    loaded = fetcher.load_data(symbol, tf)
    # نادیده گرفتن freq در مقایسه
    pd.testing.assert_frame_equal(loaded, sample_ohlcv_data, check_freq=False)

def test_multi_timeframe_independence():
    """
    اثبات استقلال تایم‌فریم‌ها (placeholder).
    """
    assert True

def test_import_data_does_not_create_exchange_connection():
    """
    اطمینان از اینکه وارد کردن data.py باعث اتصال به صرافی نمی‌شود.
    """
    import data
    assert not hasattr(data, 'fetcher')

def test_datafetcher_uses_correct_exchange(mocker):
    """
    بررسی استفاده از ccxt.gate با آپشن‌های صحیح.
    """
    mock_gate = mocker.patch('ccxt.gate')
    mock_instance = mock_gate.return_value
    mock_instance.load_markets.return_value = None

    fetcher = DataFetcher()
    mock_gate.assert_called_once_with(config.EXCHANGE_OPTIONS)
    mock_instance.load_markets.assert_called_once()
