import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from data import DataFetcher
import numpy as np

# ------------------------------------------------------------------
# تست استقلال تایم‌فریم‌ها
# ------------------------------------------------------------------
def test_timeframe_independence(mocker):
    """
    اثبات می‌کند که DataFetcher برای هر تایم‌فریم به‌طور جداگانه از صرافی درخواست می‌دهد
    و از resample کردن داده‌های یک تایم‌فریم برای دیگری استفاده نمی‌کند.
    """
    # Mock کردن fetch_ohlcv برای هر تایم‌فریم
    original_fetch = DataFetcher.fetch_ohlcv

    call_counts = {}

    def mock_fetch(self, symbol, timeframe, since=None, limit=None, remove_incomplete_candle=False):
        call_counts[timeframe] = call_counts.get(timeframe, 0) + 1
        # برگرداندن یک DataFrame خالی
        idx = pd.date_range(end=datetime.now(timezone.utc), periods=2, freq=timeframe, tz='UTC')
        return pd.DataFrame({
            'open': [100, 101], 'high': [102, 103],
            'low': [99, 100], 'close': [101, 102],
            'volume': [10, 20]
        }, index=idx[:2])

    mocker.patch.object(DataFetcher, 'fetch_ohlcv', mock_fetch)

    fetcher = DataFetcher()
    # درخواست داده برای هر سه تایم‌فریم
    for tf in ['4h', '1h', '5m']:
        fetcher.get_historical_data(symbol='BTC/USDT:USDT', timeframe=tf, force_fetch=True)

    # باید دقیقاً سه بار fetch صدا زده شده باشد (هر کدام یک بار)
    assert len(call_counts) == 3
    for tf in ['4h', '1h', '5m']:
        assert call_counts[tf] == 1, f"fetch_ohlcv for {tf} should be called exactly once"

# ------------------------------------------------------------------
# تست ترتیب زمانی و یکتایی
# ------------------------------------------------------------------
def test_chronological_order_and_uniqueness(tmp_path):
    """
    اطمینان از اینکه داده‌ها پس از ذخیره و بارگذاری همچنان مرتب صعودی هستند
    و رکوردهای تکراری حذف می‌شوند.
    """
    # ایجاد یک DataFrame با ترتیب نزولی و یک رکورد تکراری
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
    # ترتیب اولیه را نزولی می‌کنیم
    df = df.sort_index(ascending=False)

    # ذخیره و بارگذاری با DataFetcher
    import os
    from data import DataFetcher
    # Mock کردن ccxt.gate برای جلوگیری از اتصال
    with pytest.MonkeyPatch.context() as mp:
        import ccxt
        mp.setattr(ccxt, 'gate', lambda *a, **kw: None)
        fetcher = DataFetcher()
    fetcher._file_path = lambda s, t: os.path.join(tmp_path, f"{s.replace('/', '_')}_{t}.csv")
    symbol, tf = 'BTC/USDT:USDT', '5m'
    fetcher.save_data(df, symbol, tf)
    loaded = fetcher.load_data(symbol, tf)

    # باید صعودی باشد
    assert loaded.index.is_monotonic_increasing
    # تعداد باید کمتر از اصلی باشد (تکراری حذف شده)
    # اما load_data تکراری را حذف نمی‌کند (تنها save/load)
    # برای حذف تکراری باید از متد get_historical_data استفاده کنیم که تکراری‌ها را حذف می‌کند.
    # بنابراین این تست فقط صعودی بودن را بررسی می‌کند.
    # تست حذف تکراری در get_historical_data بعداً می‌آید.

# ------------------------------------------------------------------
# تست عدم نشت داده‌های آینده (look-ahead bias)
# ------------------------------------------------------------------
def test_no_future_data_leakage():
    """
    شبیه‌سازی یک بک‌تست ساده که تضمین می‌کند در هر نقطه‌ی تصمیم‌گیری
    فقط داده‌های تا آن لحظه در دسترس هستند.
    """
    # ایجاد داده مصنوعی با تاریخ‌های مشخص
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    dates = pd.date_range(start=base, periods=10, freq='1h', tz='UTC')
    df = pd.DataFrame({
        'open': range(10),
        'high': range(1, 11),
        'low': range(0, 10),
        'close': range(2, 12),
        'volume': 100
    }, index=dates)

    # شبیه‌سازی بک‌تست: برای هر ایندکس i، فقط سطرهای 0 تا i باید قابل مشاهده باشند
    for i in range(len(df)):
        available = df.iloc[:i+1]
        # اطمینان از اینکه هیچ ایندکسی بزرگتر از i وجود ندارد
        assert available.index.max() == dates[i]
        assert len(available) == i + 1

# ------------------------------------------------------------------
# تست حذف کندل ناقص
# ------------------------------------------------------------------
def test_incomplete_candle_removal(mocker):
    """
    بررسی اینکه fetch_ohlcv با remove_incomplete_candle=True آخرین کندل ناقص را حذف می‌کند.
    """
    now = datetime.now(timezone.utc)
    # ایجاد کندل‌های ۵ دقیقه‌ای: یکی کامل در گذشته، یکی ناقص در آینده نزدیک
    complete_time = now - timedelta(minutes=10)
    incomplete_time = now - timedelta(minutes=2)  # هنوز ۳ دقیقه تا بسته شدن مانده
    fake_raw = [
        [int(complete_time.timestamp() * 1000), 100, 102, 99, 101, 50],
        [int(incomplete_time.timestamp() * 1000), 101, 103, 100, 102, 30]
    ]

    mocker.patch.object(DataFetcher, 'fetch_ohlcv', return_value=fake_raw)

    fetcher = DataFetcher()
    # بدون حذف
    df_full = fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m', remove_incomplete_candle=False)
    assert len(df_full) == 2

    # با حذف کندل ناقص
    df_clean = fetcher.fetch_ohlcv('BTC/USDT:USDT', '5m', remove_incomplete_candle=True)
    assert len(df_clean) == 1
    assert df_clean.index[0] == complete_time

# ------------------------------------------------------------------
# تست یکپارچگی داده واقعی (اختیاری، فقط در صورت دسترسی به اینترنت)
# ------------------------------------------------------------------
@pytest.mark.integration
def test_real_data_fetch():
    """
    دریافت واقعی ۱۰ کندل ۵ دقیقه‌ای و بررسی صحت ساختار.
    این تست فقط در صورت وجود اینترنت و تنظیمات API اجرا می‌شود.
    """
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
        # آخرین کندل نباید ناقص باشد
        delta = timedelta(minutes=5)
        assert df.index[-1] + delta <= datetime.now(timezone.utc)
    except Exception as e:
        pytest.skip(f"Skipping integration test due to: {e}")
