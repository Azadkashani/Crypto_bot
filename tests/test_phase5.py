import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import indicators
from choch import detect_choch

# -------------------------------
# داده‌های مصنوعی کمکی
# -------------------------------
def _make_base_df(n=40):
    """DataFrame پایه با ایندکس زمانی و ستون‌های OHLCV."""
    dates = pd.date_range(start='2025-01-01', periods=n, freq='5min', tz='UTC')
    df = pd.DataFrame(index=dates)
    df['open'] = 100.0
    df['high'] = 100.0
    df['low'] = 100.0
    df['close'] = 100.0
    df['volume'] = 1000
    return df

def _make_bullish_choch_df():
    """ساختار نزولی (Lower Highs) و شکست صعودی."""
    df = _make_base_df(35)
    # سقف اول در ایندکس 10
    df.loc[df.index[7:14], 'high'] = np.nan  # ابتدا پاک کن
    df.loc[df.index[7:14], 'high'] = [100, 101, 102, 103, 110, 101, 100]  # قله 110 در ایندکس 10
    df.loc[df.index[10], 'high'] = 110
    # اطراف سقف اول
    for i in range(7, 14):
        if i != 10:
            df.loc[df.index[i], 'high'] = 100 + abs(i-10)*0.5  # کمتر از 110
    df.loc[df.index[10], 'high'] = 110
    # low ها هم متناسب
    df.loc[df.index[7:14], 'low'] = df.loc[df.index[7:14], 'high'] - 3

    # سقف دوم در ایندکس 20 (Lower High)
    df.loc[df.index[17:24], 'high'] = np.nan
    df.loc[df.index[17:24], 'high'] = [100, 101, 102, 105, 100, 99, 98]  # قله 105
    df.loc[df.index[20], 'high'] = 105
    for i in range(17, 24):
        if i != 20:
            df.loc[df.index[i], 'high'] = 100 + abs(i-20)*0.3  # کمتر از 105
    df.loc[df.index[20], 'high'] = 105
    df.loc[df.index[17:24], 'low'] = df.loc[df.index[17:24], 'high'] - 3

    # بقیه کندل‌ها: نزولی ملایم تا قبل از شکست
    for i in range(0, len(df)):
        if i not in list(range(7,14)) + list(range(17,24)):
            df.loc[df.index[i], 'high'] = 100 - i*0.2
            df.loc[df.index[i], 'low'] = df.loc[df.index[i], 'high'] - 2

    # شکست: کندل 25 بسته بالای 105
    df.loc[df.index[25], 'close'] = 106.0
    df.loc[df.index[25], 'high'] = 107.0
    df.loc[df.index[25], 'low'] = 104.0
    df.loc[df.index[25], 'open'] = 104.5

    # سایر کلوزها را هم تنظیم می‌کنیم تا قابل قبول باشند
    df['close'] = df['close'].fillna(df['high'] - 1)
    df['open'] = df['open'].fillna(df['close'] - 0.5)
    return df

def _make_bearish_choch_df():
    """ساختار صعودی (Higher Lows) و شکست نزولی."""
    df = _make_base_df(35)
    # کف اول در ایندکس 10
    df.loc[df.index[7:14], 'low'] = np.nan
    df.loc[df.index[7:14], 'low'] = [100, 99, 98, 97, 90, 98, 99]  # کف 90
    df.loc[df.index[10], 'low'] = 90
    for i in range(7, 14):
        if i != 10:
            df.loc[df.index[i], 'low'] = 100 - abs(i-10)*0.5
    df.loc[df.index[10], 'low'] = 90
    df.loc[df.index[7:14], 'high'] = df.loc[df.index[7:14], 'low'] + 3

    # کف دوم در ایندکس 20 (Higher Low)
    df.loc[df.index[17:24], 'low'] = np.nan
    df.loc[df.index[17:24], 'low'] = [100, 101, 102, 95, 101, 102, 103]  # کف 95
    df.loc[df.index[20], 'low'] = 95
    for i in range(17, 24):
        if i != 20:
            df.loc[df.index[i], 'low'] = 100 + abs(i-20)*0.3
    df.loc[df.index[20], 'low'] = 95
    df.loc[df.index[17:24], 'high'] = df.loc[df.index[17:24], 'low'] + 3

    # بقیه کندل‌ها: صعودی ملایم
    for i in range(0, len(df)):
        if i not in list(range(7,14)) + list(range(17,24)):
            df.loc[df.index[i], 'low'] = 100 + i*0.2
            df.loc[df.index[i], 'high'] = df.loc[df.index[i], 'low'] + 2

    # شکست: کندل 25 بسته زیر 95
    df.loc[df.index[25], 'close'] = 94.0
    df.loc[df.index[25], 'low'] = 93.0
    df.loc[df.index[25], 'high'] = 96.0
    df.loc[df.index[25], 'open'] = 95.5

    df['close'] = df['close'].fillna(df['low'] + 1)
    df['open'] = df['open'].fillna(df['close'] + 0.5)
    return df


# -------------------------------
# تست‌ها
# -------------------------------
def test_bullish_choch_detected():
    df = _make_bullish_choch_df()
    df = detect_choch(df)
    # انتظار داریم در کندل 25 (شکست) bullish_choch True باشد
    assert df.loc[df.index[25], 'bullish_choch'] == True
    # اطمینان از اینکه CHOCH نزولی رخ نداده است
    assert df['bearish_choch'].sum() == 0

def test_bearish_choch_detected():
    df = _make_bearish_choch_df()
    df = detect_choch(df)
    assert df.loc[df.index[25], 'bearish_choch'] == True
    assert df['bullish_choch'].sum() == 0

def test_wick_only_break_does_not_trigger_choch():
    # ساخت داده صعودی CHOCH اما در کندل شکست، کلوز زیر سطح باقی می‌ماند
    df = _make_bullish_choch_df()
    # اصلاح کندل 25: سایه بالا از سطح عبور می‌کند ولی کلوز زیر 105
    df.loc[df.index[25], 'high'] = 106.0   # سطح شکسته شده با سایه
    df.loc[df.index[25], 'close'] = 104.5  # کلوز زیر 105
    df = detect_choch(df)
    assert df.loc[df.index[25], 'bullish_choch'] == False
    assert df['bullish_choch'].sum() == 0

def test_incomplete_candle_does_not_trigger_choch():
    # داده کامل تا قبل از کندل شکست
    df = _make_bullish_choch_df()
    df_incomplete = df.iloc[:25]  # تا ایندکس 24 (شکست هنوز نیامده)
    df_incomplete = detect_choch(df_incomplete)
    assert df_incomplete['bullish_choch'].sum() == 0

def test_no_lookahead():
    # ساخت داده با شکست، سپس چند کندل آینده اضافه می‌کنیم و بررسی می‌کنیم
    df = _make_bullish_choch_df()
    df_detected = detect_choch(df)
    # ایندکس شکست
    break_idx = df.index[25]
    # اگر فقط تا ایندکس 25 را بدهیم، باید همان نتیجه را بدهد
    partial = df.iloc[:26]
    partial_detected = detect_choch(partial)
    assert df_detected.loc[break_idx, 'bullish_choch'] == True
    assert partial_detected.loc[break_idx, 'bullish_choch'] == True
    # اطمینان از اینکه کندل‌های بعدی تأثیری روی تشخیص قبلی ندارند
    assert df_detected['bullish_choch'].sum() == 1  # فقط همان یک کندل

def test_direction_correctness():
    # داده صعودی و نزولی جدا
    bull_df = detect_choch(_make_bullish_choch_df())
    bear_df = detect_choch(_make_bearish_choch_df())
    # هیچ تداخلی وجود ندارد
    assert bull_df['bearish_choch'].sum() == 0
    assert bear_df['bullish_choch'].sum() == 0

def test_uses_confirmed_swings_only():
    # اطمینان از اینکه ستون‌های swing در خروجی وجود دارند و همان مقادیر detect_swings هستند
    df = _make_bullish_choch_df()
    df_swings = indicators.detect_swings(df)
    df_choch = detect_choch(df)
    pd.testing.assert_series_equal(df_choch['swing_high'], df_swings['swing_high'])
    pd.testing.assert_series_equal(df_choch['swing_low'], df_swings['swing_low'])
