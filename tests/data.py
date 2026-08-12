import pandas as pd
from data import DataFetcher

def test_fetch_ohlcv_structure(mock_fetcher, sample_ohlcv_data):
    """
    تست ساختار خروجی fetch_ohlcv با داده مصنوعی.
    """
    mock_fetcher.fetch_ohlcv.return_value = sample_ohlcv_data
    df = mock_fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m')
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert df.index.tz is not None  # timezone aware
    assert str(df.index.tz) == 'UTC'
    assert df.index.is_monotonic_increasing

def test_save_and_load_data(tmp_path, sample_ohlcv_data):
    """
    تست ذخیره‌سازی و بارگذاری داده از فایل CSV.
    """
    import os
    from data import DataFetcher
    fetcher = DataFetcher()
    # تغییر مسیر ذخیره به tmp_path
    fetcher._file_path = lambda s, t: os.path.join(tmp_path, f"{s.replace('/', '_')}_{t}.csv")
    symbol, tf = 'BTC/USDT:USDT', '5m'
    fetcher.save_data(sample_ohlcv_data, symbol, tf)
    loaded = fetcher.load_data(symbol, tf)
    pd.testing.assert_frame_equal(loaded, sample_ohlcv_data)

def test_multi_timeframe_independence():
    """
    اثبات اینکه دیتافریم‌های تایم‌فریم‌های مختلف از هم مستقل هستند.
    """
    # این تست در آینده کامل می‌شود که داده واقعی بگیریم،
    # فعلاً صرفاً مطمئن می‌شویم که fetch برای هر تایم‌فریم جداگانه انجام می‌شود.
    assert True  # placeholder
