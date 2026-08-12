import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import strategy
import config
import indicators
import regime
import choch
import bos

# ---------- توابع کمکی برای داده مصنوعی ----------
def _make_base_df(n, freq='5min'):
    dates = pd.date_range(start='2025-01-01', periods=n, freq=freq, tz='UTC')
    df = pd.DataFrame(index=dates)
    df['open'] = 100.0
    df['high'] = 100.0
    df['low'] = 100.0
    df['close'] = 100.0
    df['volume'] = 1000
    return df

def _make_bullish_regime_df(n=300):
    """ساخت دیتافریم 4h/1h صعودی برای رژیم."""
    dates = pd.date_range(start='2025-01-01', periods=n, freq='4h', tz='UTC')
    close = 100 + np.arange(n) * 0.5
    df = pd.DataFrame({
        'open': close - 0.1,
        'high': close + 0.5,
        'low': close - 0.5,
        'close': close,
        'volume': 100
    }, index=dates)
    return df

def _make_bearish_regime_df(n=300):
    dates = pd.date_range(start='2025-01-01', periods=n, freq='4h', tz='UTC')
    close = 100 - np.arange(n) * 0.5
    df = pd.DataFrame({
        'open': close + 0.1,
        'high': close + 0.5,
        'low': close - 0.5,
        'close': close,
        'volume': 100
    }, index=dates)
    return df

def _make_5m_long_setup():
    """ساخت دیتافریم 5m با پولبک، RSI oversold، CHOCH و BOS صعودی."""
    n = 45
    idx = pd.date_range(start='2025-01-01', periods=n, freq='5min', tz='UTC')
    df = pd.DataFrame(index=idx)
    # قیمت پایه روند نزولی برای RSI < 30
    closes = []
    for i in range(14):
        closes.append(100 - i * 2)   # i=13 => 74
    for i in range(14, 18):
        closes.append(74 + (i - 13) * 1)  # i=17 => 78
    # بعداً برای CHOCH/BOS تعدیل می‌شود
    # مقادیر موقت
    df['close'] = closes + [80, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94][:n]
    # اما بهتر است آرایه کامل برای 45
    # به دلیل طول، از لیست کامل استفاده می‌کنیم
    full_closes = [100-i*2 for i in range(14)]  # 100..74
    full_closes += [75, 77, 79, 80, 78, 76, 74, 72, 70, 68, 66, 64, 62, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77]  # fill later
    # چون n=45 و فعلاً 14+...=؟
    # ساده‌سازی: از آرایه کامل زیر استفاده می‌کنیم
    closes_full = [
        100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74,  # downtrend RSI <30
        75, 77, 79, 81, 83, 85, 84, 83, 82, 81, 80, 79, 78, 77,   # recovery and lower high region
        80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 110  # up after CHOCH/BOS
    ]
    # طول closes_full=14+14+16=44? نه
    # صرف‌نظر از دقت، از لیست با طول 45 استفاده می‌کنیم
    closes_full = [
        100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74,
        75, 77, 79, 81, 83, 85, 84, 82, 80, 78, 76, 74, 72, 70,
        72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 102, 104
    ]
    df['close'] = closes_full
    # های/لو پیش‌فرض
    df['high'] = df['close'] + 1
    df['low'] = df['close'] - 1
    df['open'] = df['close'] - 0.5

    # تنظیم نوسان‌های خاص
    # سقف اول در ایندکس 8: high=86 (بالاتر از اطراف)
    df.loc[df.index[8], 'high'] = 86.0
    df.loc[df.index[8], 'low'] = 82.0
    df.loc[df.index[8], 'close'] = 84.0
    df.loc[df.index[8], 'open'] = 83.5
    # سقف دوم (Lower High) در ایندکس 18: high=82
    df.loc[df.index[18], 'high'] = 82.0
    df.loc[df.index[18], 'low'] = 78.0
    df.loc[df.index[18], 'close'] = 80.0
    df.loc[df.index[18], 'open'] = 79.5
    # کندل CHOCH در 22: بسته بالای 82
    df.loc[df.index[22], 'open'] = 81.0
    df.loc[df.index[22], 'high'] = 84.0
    df.loc[df.index[22], 'low'] = 80.0
    df.loc[df.index[22], 'close'] = 83.0
    # نوسان بالای جدید در 28: high=88
    df.loc[df.index[28], 'open'] = 85.0
    df.loc[df.index[28], 'high'] = 88.0
    df.loc[df.index[28], 'low'] = 84.0
    df.loc[df.index[28], 'close'] = 86.0
    # کندل BOS در 32: بسته بالای 88
    df.loc[df.index[32], 'open'] = 87.0
    df.loc[df.index[32], 'high'] = 90.0
    df.loc[df.index[32], 'low'] = 85.0
    df.loc[df.index[32], 'close'] = 89.0
    # بقیه کندل‌ها بعد از 32، بالای سطح
    df.loc[df.index[33:], 'close'] = 90.0
    df.loc[df.index[33:], 'high'] = 91.0
    df.loc[df.index[33:], 'low'] = 89.0
    df.loc[df.index[33:], 'open'] = 89.5

    return df

def _make_5m_short_setup():
    """ساخت دیتافریم 5m با پولبک صعودی، RSI overbought، CHOCH و BOS نزولی."""
    n = 45
    idx = pd.date_range(start='2025-01-01', periods=n, freq='5min', tz='UTC')
    df = pd.DataFrame(index=idx)
    # روند صعودی برای RSI > 70
    closes_full = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126,
        125, 123, 121, 119, 117, 115, 116, 118, 120, 122, 124, 126, 128, 130,
        128, 126, 124, 122, 120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 98, 96
    ]
    df['close'] = closes_full
    df['high'] = df['close'] + 1
    df['low'] = df['close'] - 1
    df['open'] = df['close'] + 0.5

    # کف اول در ایندکس 8: low=114
    df.loc[df.index[8], 'low'] = 114.0
    df.loc[df.index[8], 'high'] = 118.0
    df.loc[df.index[8], 'close'] = 116.0
    df.loc[df.index[8], 'open'] = 116.5
    # کف دوم (Higher Low) در 18: low=118
    df.loc[df.index[18], 'low'] = 118.0
    df.loc[df.index[18], 'high'] = 122.0
    df.loc[df.index[18], 'close'] = 120.0
    df.loc[df.index[18], 'open'] = 120.5
    # کندل CHOCH در 22: بسته زیر 118
    df.loc[df.index[22], 'open'] = 119.0
    df.loc[df.index[22], 'high'] = 120.0
    df.loc[df.index[22], 'low'] = 116.0
    df.loc[df.index[22], 'close'] = 117.0
    # نوسان پایین جدید در 28: low=112
    df.loc[df.index[28], 'open'] = 115.0
    df.loc[df.index[28], 'high'] = 116.0
    df.loc[df.index[28], 'low'] = 112.0
    df.loc[df.index[28], 'close'] = 114.0
    # کندل BOS در 32: بسته زیر 112
    df.loc[df.index[32], 'open'] = 113.0
    df.loc[df.index[32], 'high'] = 114.0
    df.loc[df.index[32], 'low'] = 110.0
    df.loc[df.index[32], 'close'] = 111.0
    # بقیه زیر سطح
    df.loc[df.index[33:], 'close'] = 110.0
    df.loc[df.index[33:], 'high'] = 111.0
    df.loc[df.index[33:], 'low'] = 109.0
    df.loc[df.index[33:], 'open'] = 110.5

    return df


# ---------- تست‌ها ----------
def test_long_requires_4h_and_1h_bullish():
    df_4h = _make_bearish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"
    assert res["valid"] is False

def test_short_requires_4h_and_1h_bearish():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bearish_regime_df()
    df_5m = _make_5m_short_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"

def test_no_signal_when_timeframes_not_aligned():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bearish_regime_df()
    df_5m = _make_5m_long_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"

def test_long_rsi_pullback_and_recovery():
    # بدون CHOCH/BOS اما RSI باید شرط را داشته باشد
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # فقط تا قبل از CHOCH (شاخص 21) بررسی RSI
    partial = df_5m.iloc[:22]
    # محاسبه RSI
    rsi_df = indicators.add_rsi(partial, period=config.RSI_PERIOD)
    rsi_series = rsi_df[f'rsi_{config.RSI_PERIOD}'].dropna()
    assert rsi_series.min() <= config.RSI_OVERSOLD
    assert rsi_series.iloc[-1] > rsi_series.iloc[-2]

def test_short_rsi_pullback_and_recovery():
    df_4h = _make_bearish_regime_df()
    df_1h = _make_bearish_regime_df()
    df_5m = _make_5m_short_setup()
    partial = df_5m.iloc[:22]
    rsi_df = indicators.add_rsi(partial, period=config.RSI_PERIOD)
    rsi_series = rsi_df[f'rsi_{config.RSI_PERIOD}'].dropna()
    assert rsi_series.max() >= config.RSI_OVERBOUGHT
    assert rsi_series.iloc[-1] < rsi_series.iloc[-2]

def test_long_requires_choch_before_bos():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # حذف CHOCH از داده با تغییر ساختار؟ ساده: df بدون CHOCH ولی BOS ممکن نیست
    # بنابراین تست با داده‌ای که CHOCH نداشته باشد
    # از همان داده تا قبل از CHOCH استفاده می‌کنیم
    partial = df_5m.iloc[:22]  # تا قبل از CHOCH
    res = strategy.generate_signal(df_4h, df_1h, partial)
    assert res["signal"] == "NONE"
    assert "CHOCH not detected" in res["reason"]

def test_short_requires_choch_before_bos():
    df_4h = _make_bearish_regime_df()
    df_1h = _make_bearish_regime_df()
    df_5m = _make_5m_short_setup()
    partial = df_5m.iloc[:22]
    res = strategy.generate_signal(df_4h, df_1h, partial)
    assert res["signal"] == "NONE"

def test_long_signal_after_rsi_choch_bos():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "LONG"
    assert res["valid"] is True
    assert res["choch"] is True
    assert res["bos"] is True

def test_short_signal_after_rsi_choch_bos():
    df_4h = _make_bearish_regime_df()
    df_1h = _make_bearish_regime_df()
    df_5m = _make_5m_short_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "SHORT"
    assert res["valid"] is True

def test_incomplete_5m_candle_not_used():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # آخرین کندل ناقص را اضافه می‌کنیم: زمان now را بعد از شروع آخرین کندل و قبل از بسته شدنش
    last_start = df_5m.index[-1]
    as_of = last_start + timedelta(minutes=2)  # هنوز 3 دقیقه مانده
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    # آخرین کندل بسته‌شده قبل از as_of را در نظر بگیرد، نه کندل ناقص
    # در اینجا as_of قبل از بسته شدن آخرین کندل است
    assert res["signal"] == "NONE"  # چون آخرین کندل کامل ایندکس 43 است و BOS در 44 (ناقص) نیست

def test_incomplete_1h_candle_not_used():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # 1h دیتافریم با آخرین کندل ناقص
    as_of = df_1h.index[-1] + timedelta(minutes=30)
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    # رژیم 1h باید بر اساس کندل بسته‌شده قبلی باشد؛ سیگنال ممکن است NO چون زمان ناقص است
    assert res["signal"] == "NONE"  # اگر as_of قبل از بسته شدن آخرین 1h باشد، داده آخرین کامل قبلی است

def test_incomplete_4h_candle_not_used():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    as_of = df_4h.index[-1] + timedelta(hours=2)
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    assert res["signal"] == "NONE"

def test_no_future_data_used():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # سیگنال فقط با داده تا ایندکس 32 (کندل BOS) باید LONG باشد
    as_of = df_5m.index[32] + timedelta(minutes=5)  # دقیقاً بعد از بسته شدن 32
    res_before = strategy.generate_signal(df_4h, df_1h, df_5m.iloc[:33], as_of=df_5m.index[32] + timedelta(minutes=5))
    assert res_before["signal"] == "LONG"

def test_wick_only_bos_not_signal():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m = _make_5m_long_setup()
    # در کندل BOS (32)، سایه بالا از سطح 88 عبور می‌کند اما کلوز زیر 88
    df_5m.loc[df_5m.index[32], 'high'] = 90.0
    df_5m.loc[df_5m.index[32], 'close'] = 87.5
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"
    assert res["bos"] is False

def test_timeframe_dataframes_are_independent():
    df_4h = _make_bullish_regime_df()
    df_1h = _make_bullish_regime_df()
    df_5m_long = _make_5m_long_setup()
    df_5m_short = _make_5m_short_setup()
    # استقلال: دیتافریم‌های مختلف باید نتایج متفاوت بدهند
    res_long = strategy.generate_signal(df_4h, df_1h, df_5m_long)
    res_short = strategy.generate_signal(df_4h, df_1h, df_5m_short)
    assert res_long["signal"] != res_short["signal"]
