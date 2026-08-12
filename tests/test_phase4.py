import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import regime
import config

# توابع کمکی برای ساخت داده مصنوعی
def _make_uptrend(n=300, start_price=100.0, step=0.5):
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h', tz='UTC')
    close = start_price + np.arange(n) * step
    high = close + 0.2
    low = close - 0.2
    open_ = close - 0.1
    volume = 100
    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)

def _make_downtrend(n=300, start_price=100.0, step=0.5):
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h', tz='UTC')
    close = start_price - np.arange(n) * step
    high = close + 0.2
    low = close - 0.2
    open_ = close + 0.1
    volume = 100
    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)

def _make_range(n=300, center=100.0, noise=0.1):
    np.random.seed(0)
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h', tz='UTC')
    close = center + np.random.normal(0, noise, n)
    high = close + 0.2
    low = close - 0.2
    open_ = close - 0.1
    volume = 100
    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


# 1. رژیم صعودی
def test_bullish_regime():
    df = _make_uptrend()
    assert regime.get_regime(df) == regime.REGIME_BULLISH

# 2. رژیم نزولی
def test_bearish_regime():
    df = _make_downtrend()
    assert regime.get_regime(df) == regime.REGIME_BEARISH

# 3. رژیم رنج
def test_range_regime():
    df = _make_range()
    assert regime.get_regime(df) == regime.REGIME_RANGE

# 4. هم‌راستایی صعودی
def test_aligned_bullish():
    assert regime.regimes_aligned(regime.REGIME_BULLISH, regime.REGIME_BULLISH) == "aligned_bullish"

# 5. هم‌راستایی نزولی
def test_aligned_bearish():
    assert regime.regimes_aligned(regime.REGIME_BEARISH, regime.REGIME_BEARISH) == "aligned_bearish"

# 6. ترکیب صعودی + نزولی => عدم هم‌راستایی
def test_not_aligned_bull_bear():
    assert regime.regimes_aligned(regime.REGIME_BULLISH, regime.REGIME_BEARISH) == "not_aligned"

# 7. ترکیب رنج + صعودی => عدم هم‌راستایی
def test_not_aligned_range_bull():
    assert regime.regimes_aligned(regime.REGIME_RANGE, regime.REGIME_BULLISH) == "not_aligned"

# 8. عدم استفاده از داده آینده
def test_no_future_candle_used():
    # ساخت داده صعودی و سپس معکوس به نزولی
    df = _make_uptrend(n=200)
    # نقطه 100 هنوز در فاز صعودی است
    prefix_100 = df.iloc[:101]
    # رژیم در ایندکس 100 باید صعودی باشد
    assert regime.get_regime(prefix_100) == regime.REGIME_BULLISH

    # اضافه کردن 99 کندل نزولی بعد از ایندکس 100
    bearish_part = _make_downtrend(n=100, start_price=df['close'].iloc[100], step=0.5)
    combined = pd.concat([df.iloc[:101], bearish_part])
    # رژیم در انتهای داده ترکیبی ممکن است متفاوت باشد (تأیید می‌شود که تابع به کل داده و آخرین کندل نگاه می‌کند)
    # اما برای نقطه 100، باید همچنان با همان داده قبلی محاسبه شود
    prefix_100_from_combined = combined.iloc[:101]
    assert regime.get_regime(prefix_100_from_combined) == regime.REGIME_BULLISH

# 9. استقلال تایم‌فریم‌ها
def test_timeframe_independence():
    df_4h = _make_uptrend(n=100)
    df_1h = _make_downtrend(n=100)
    r_4h = regime.get_regime(df_4h)
    r_1h = regime.get_regime(df_1h)
    assert r_4h == regime.REGIME_BULLISH
    assert r_1h == regime.REGIME_BEARISH
    # عدم تداخل
    assert r_4h != r_1h
