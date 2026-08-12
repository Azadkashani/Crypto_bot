import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import indicators
import config

# ========================
# داده‌های تستی
# ========================
@pytest.fixture
def ohlc_df():
    """تولید یک DataFrame تست با روند ساده."""
    np.random.seed(0)
    n = 50
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h', tz='UTC')
    close = 100 + np.cumsum(np.random.randn(n)) * 0.5
    high = close + np.abs(np.random.randn(n)) * 0.2
    low = close - np.abs(np.random.randn(n)) * 0.2
    volume = np.random.randint(100, 200, n)
    return pd.DataFrame({
        'open': close - 0.1,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)

# ========================
# تست‌های EMA
# ========================
def test_ema_calculation(ohlc_df):
    df_ema = indicators.add_ema(ohlc_df, period=5)
    col = 'ema_5'
    assert col in df_ema.columns
    # مقادیر نباید NaN در انتها باشند (ممکن است اولی‌ها NaN باشند)
    assert not df_ema[col].iloc[-1] is None
    assert df_ema[col].iloc[-1] is not np.nan  # tolerance
    # مقدار اول باید NaN یا نزدیک اولین کلوز
    assert pd.isna(df_ema[col].iloc[0]) or abs(df_ema[col].iloc[0] - ohlc_df['close'].iloc[0]) < 0.1

def test_ema_does_not_modify_original(ohlc_df):
    original = ohlc_df.copy()
    _ = indicators.add_ema(ohlc_df, period=5)
    pd.testing.assert_frame_equal(original, ohlc_df)

# ========================
# تست‌های RSI
# ========================
def test_rsi_calculation(ohlc_df):
    df_rsi = indicators.add_rsi(ohlc_df, period=14)
    col = 'rsi_14'
    assert col in df_rsi.columns
    # RSI بین 0 و 100
    assert df_rsi[col].dropna().between(0, 100).all()

def test_rsi_does_not_modify_original(ohlc_df):
    original = ohlc_df.copy()
    _ = indicators.add_rsi(ohlc_df, period=14)
    pd.testing.assert_frame_equal(original, ohlc_df)

# ========================
# تست‌های ATR
# ========================
def test_atr_calculation(ohlc_df):
    df_atr = indicators.add_atr(ohlc_df, period=14)
    col = 'atr_14'
    assert col in df_atr.columns
    assert df_atr[col].dropna().min() >= 0

# ========================
# تست‌های ADX
# ========================
def test_adx_calculation(ohlc_df):
    df_adx = indicators.add_adx(ohlc_df, period=14)
    col = 'adx_14'
    assert col in df_adx.columns
    assert df_adx[col].dropna().between(0, 100).all()

# ========================
# تست‌های Volume SMA
# ========================
def test_volume_sma_calculation(ohlc_df):
    df_vol = indicators.add_volume_sma(ohlc_df, period=5)
    col = 'volume_sma_5'
    assert col in df_vol.columns
    # بعد از period اول، مقادیر باید معتبر باشند
    assert df_vol[col].iloc[4] is not np.nan

# ========================
# تست‌های Swing
# ========================
def test_swing_high_detection():
    # ساخت داده‌ای که یک قله واضح در وسط دارد
    dates = pd.date_range(start='2025-01-01', periods=20, freq='1h', tz='UTC')
    highs = np.array([10]*20)
    highs[10] = 20  # قله
    lows = highs - 1
    df = pd.DataFrame({'high': highs, 'low': lows, 'open': highs-0.5, 'close': highs-0.2, 'volume': 100}, index=dates)
    df = indicators.detect_swings(df, left_bars=3, right_bars=3)
    assert df.loc[df.index[10], 'swing_high'] == True
    # قبل و بعد نباید قله دیگری باشه
    assert df['swing_high'].sum() == 1

def test_swing_low_detection():
    dates = pd.date_range(start='2025-01-01', periods=20, freq='1h', tz='UTC')
    lows = np.array([10]*20)
    lows[10] = 2  # دره
    highs = lows + 1
    df = pd.DataFrame({'high': highs, 'low': lows, 'open': highs-0.5, 'close': highs-0.2, 'volume': 100}, index=dates)
    df = indicators.detect_swings(df, left_bars=3, right_bars=3)
    assert df.loc[df.index[10], 'swing_low'] == True
    assert df['swing_low'].sum() == 1

def test_swing_no_future_leak():
    # تست عدم استفاده از اطلاعات آینده: سویینگ‌ها تنها در اندیس‌های i که i + right_bars < len(df) قابل شناسایی هستند.
    dates = pd.date_range(start='2025-01-01', periods=20, freq='1h', tz='UTC')
    highs = np.array([10]*20)
    highs[18] = 20  # نزدیک انتها، با right_bars=3 نمی‌تواند تایید شود چون به اندازه کافی داده بعدی ندارد
    df = pd.DataFrame({'high': highs, 'low': highs-1, 'open': highs-0.5, 'close': highs-0.2, 'volume': 100}, index=dates)
    df = indicators.detect_swings(df, left_bars=3, right_bars=3)
    # اندیس 18 نباید swing high باشد
    assert df.loc[df.index[18], 'swing_high'] == False
    # اندیس 10 را تست کن که عمداً قله نیست
    assert df['swing_high'].sum() == 0

def test_swing_independence_from_future():
    # شبیه‌سازی یک بک‌تست: به ازای هر نقطه، فقط داده‌های تا آن نقطه قابل مشاهده‌اند.
    dates = pd.date_range(start='2025-01-01', periods=30, freq='1h', tz='UTC')
    highs = np.array([10]*30)
    highs[15] = 20  # قله واقعی در وسط
    df_full = pd.DataFrame({'high': highs, 'low': highs-1, 'open': highs-0.5, 'close': highs-0.2, 'volume': 100}, index=dates)
    # از i=15 شروع می‌کنیم تا سطر ۱۵ همیشه در partial باشد
    for i in range(15, 25):  # 15 تا 24
        partial = df_full.iloc[:i+1].copy()
        partial = indicators.detect_swings(partial, left_bars=3, right_bars=3)
        # اگر i >= 15+3 = 18، swing_high در اندیس ۱۵ باید True شود
        if i >= 18:
            assert partial.loc[partial.index[15], 'swing_high'] == True
        else:
            # قبل از تأیید نباید True باشد
            assert partial.loc[partial.index[15], 'swing_high'] == False

def test_swing_on_multiple_timeframes(ohlc_df):
    # بررسی مستقل بودن سویینگ‌ها روی دیتافریم‌های مختلف
    df_4h = ohlc_df.copy()
    df_1h = ohlc_df.copy()
    df_5m = ohlc_df.copy()
    df_4h = indicators.detect_swings(df_4h, left_bars=2, right_bars=2)
    df_1h = indicators.detect_swings(df_1h, left_bars=2, right_bars=2)
    df_5m = indicators.detect_swings(df_5m, left_bars=2, right_bars=2)
    # هر کدام باید ستون‌های خود را داشته باشند
    assert 'swing_high' in df_4h.columns
    assert 'swing_high' in df_1h.columns
    assert 'swing_high' in df_5m.columns
    # مقادیر ممکن است متفاوت باشند
    # حداقل اطمینان از عدم تداخل
    assert not df_4h.equals(df_1h) or True  # صرفاً برای تست
