import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import indicators
from choch import detect_choch
from bos import detect_bos

# توابع کمکی برای ساخت داده‌های مصنوعی
def _make_base_df(n=40):
    dates = pd.date_range(start='2025-01-01', periods=n, freq='5min', tz='UTC')
    df = pd.DataFrame(index=dates)
    df['open'] = 100.0
    df['high'] = 100.0
    df['low'] = 100.0
    df['close'] = 100.0
    df['volume'] = 1000
    return df


def _make_bullish_choch_then_bos():
    """ساختار: روند نزولی -> CHOCH صعودی -> نوسان بالای جدید -> شکست (BOS)."""
    df = _make_base_df(35)

    # فاز نزولی با دو سقف Lower High (برای CHOCH)
    # سقف اول در ایندکس 10 با سطح 110
    df.loc[df.index[10], 'high'] = 110
    df.loc[df.index[10], 'low'] = 105
    df.loc[df.index[10], 'close'] = 106
    # اطرافش پایین‌تر
    for i in range(7, 14):
        if i != 10:
            df.loc[df.index[i], 'high'] = 100 + abs(i-10)*0.5
            df.loc[df.index[i], 'low'] = df.loc[df.index[i], 'high'] - 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'high'] - 1

    # سقف دوم در ایندکس 20 با سطح 105 (Lower High)
    df.loc[df.index[20], 'high'] = 105
    df.loc[df.index[20], 'low'] = 101
    df.loc[df.index[20], 'close'] = 102
    for i in range(17, 24):
        if i != 20:
            df.loc[df.index[i], 'high'] = 100 + abs(i-20)*0.3
            df.loc[df.index[i], 'low'] = df.loc[df.index[i], 'high'] - 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'high'] - 1

    # کندل شکست CHOCH در ایندکس 25: بسته بالای 105
    df.loc[df.index[25], 'open'] = 104
    df.loc[df.index[25], 'high'] = 107
    df.loc[df.index[25], 'low'] = 103
    df.loc[df.index[25], 'close'] = 106  # بالای 105

    # بعد از CHOCH: ساختار صعودی جدید
    # نوسان بالای جدید در ایندکس 28 با سطح 108
    df.loc[df.index[28], 'high'] = 108
    df.loc[df.index[28], 'low'] = 104
    df.loc[df.index[28], 'close'] = 105
    for i in range(25, 31):
        if i not in [25, 28]:
            df.loc[df.index[i], 'high'] = 103 + abs(i-28)*0.5
            df.loc[df.index[i], 'low'] = df.loc[df.index[i], 'high'] - 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'high'] - 1

    # کندل BOS در ایندکس 30: بسته بالای 108
    df.loc[df.index[30], 'open'] = 107
    df.loc[df.index[30], 'high'] = 110
    df.loc[df.index[30], 'low'] = 106
    df.loc[df.index[30], 'close'] = 109  # بالای 108

    # بقیه کندل‌ها (بعد از 30) بی‌اثر برای تست
    for i in range(31, len(df)):
        df.loc[df.index[i], 'high'] = 109 + (i-30)*0.1
        df.loc[df.index[i], 'low'] = df.loc[df.index[i], 'high'] - 1
        df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'high'] - 0.5

    return df


def _make_bearish_choch_then_bos():
    """ساختار: روند صعودی -> CHOCH نزولی -> نوسان پایین جدید -> شکست (BOS)."""
    df = _make_base_df(35)

    # فاز صعودی با دو کف Higher Low (برای CHOCH)
    # کف اول در ایندکس 10 با سطح 90
    df.loc[df.index[10], 'low'] = 90
    df.loc[df.index[10], 'high'] = 95
    df.loc[df.index[10], 'close'] = 94
    for i in range(7, 14):
        if i != 10:
            df.loc[df.index[i], 'low'] = 100 - abs(i-10)*0.5
            df.loc[df.index[i], 'high'] = df.loc[df.index[i], 'low'] + 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'low'] + 1

    # کف دوم در ایندکس 20 با سطح 95 (Higher Low)
    df.loc[df.index[20], 'low'] = 95
    df.loc[df.index[20], 'high'] = 99
    df.loc[df.index[20], 'close'] = 98
    for i in range(17, 24):
        if i != 20:
            df.loc[df.index[i], 'low'] = 100 + abs(i-20)*0.3
            df.loc[df.index[i], 'high'] = df.loc[df.index[i], 'low'] + 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'low'] + 1

    # کندل شکست CHOCH در ایندکس 25: بسته زیر 95
    df.loc[df.index[25], 'open'] = 97
    df.loc[df.index[25], 'high'] = 98
    df.loc[df.index[25], 'low'] = 93
    df.loc[df.index[25], 'close'] = 94  # زیر 95

    # بعد از CHOCH: ساختار نزولی جدید
    # نوسان پایین جدید در ایندکس 28 با سطح 92
    df.loc[df.index[28], 'low'] = 92
    df.loc[df.index[28], 'high'] = 96
    df.loc[df.index[28], 'close'] = 95
    for i in range(25, 31):
        if i not in [25, 28]:
            df.loc[df.index[i], 'low'] = 97 - abs(i-28)*0.5
            df.loc[df.index[i], 'high'] = df.loc[df.index[i], 'low'] + 2
            df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'low'] + 1

    # کندل BOS در ایندکس 30: بسته زیر 92
    df.loc[df.index[30], 'open'] = 94
    df.loc[df.index[30], 'high'] = 95
    df.loc[df.index[30], 'low'] = 90
    df.loc[df.index[30], 'close'] = 91  # زیر 92

    for i in range(31, len(df)):
        df.loc[df.index[i], 'low'] = 91 - (i-30)*0.1
        df.loc[df.index[i], 'high'] = df.loc[df.index[i], 'low'] + 1
        df.loc[df.index[i], 'close'] = df.loc[df.index[i], 'low'] + 0.5

    return df


# -------------------------------
# تست‌ها
# -------------------------------
def test_bullish_bos_detected():
    df = _make_bullish_choch_then_bos()
    df = detect_bos(df)
    # BOS باید در کندل 30 اتفاق بیفتد
    assert df.loc[df.index[30], 'bullish_bos'] == True
    # BOS نزولی نباید رخ دهد
    assert df['bearish_bos'].sum() == 0

def test_bearish_bos_detected():
    df = _make_bearish_choch_then_bos()
    df = detect_bos(df)
    assert df.loc[df.index[30], 'bearish_bos'] == True
    assert df['bullish_bos'].sum() == 0

def test_choch_is_not_bos():
    df = _make_bullish_choch_then_bos()
    # فقط تا کندل شکست CHOCH (25) را می‌دهیم
    partial = df.iloc[:26]
    partial = detect_bos(partial)
    # در کندل 25 که CHOCH رخ داده، نباید BOS باشد
    assert partial.loc[partial.index[25], 'bullish_bos'] == False
    assert partial['bullish_bos'].sum() == 0

def test_wick_only_break_does_not_trigger_bos():
    df = _make_bullish_choch_then_bos()
    # اصلاح کندل 30: سایه بالا از سطح 108 عبور می‌کند ولی کلوز زیر 108
    df.loc[df.index[30], 'high'] = 109.5
    df.loc[df.index[30], 'close'] = 107.5  # زیر 108
    df = detect_bos(df)
    assert df.loc[df.index[30], 'bullish_bos'] == False
    assert df['bullish_bos'].sum() == 0

def test_incomplete_candle_does_not_trigger_bos():
    df = _make_bullish_choch_then_bos()
    # فقط تا ایندکس 29 (قبل از کندل BOS) می‌دهیم
    partial = df.iloc[:30]
    partial = detect_bos(partial)
    assert partial['bullish_bos'].sum() == 0

def test_no_lookahead():
    df = _make_bullish_choch_then_bos()
    full = detect_bos(df)
    # ایندکس 30 BOS دارد
    assert full.loc[full.index[30], 'bullish_bos'] == True
    # اگر فقط تا ایندکس 30 داشته باشیم، همان نتیجه
    partial = df.iloc[:31]
    partial_detected = detect_bos(partial)
    assert partial_detected.loc[partial.index[30], 'bullish_bos'] == True
    # کندل‌های آینده نباید روی BOS قبلی اثر بگذارند
    assert full['bullish_bos'].sum() == 1  # فقط یک BOS

def test_direction_correctness():
    bull_df = detect_bos(_make_bullish_choch_then_bos())
    bear_df = detect_bos(_make_bearish_choch_then_bos())
    assert bull_df['bearish_bos'].sum() == 0
    assert bear_df['bullish_bos'].sum() == 0

def test_duplicate_prevention():
    df = _make_bullish_choch_then_bos()
    # بعد از BOS، چند کندل دیگر بالای سطح باقی بمانند
    for i in range(31, 35):
        df.loc[df.index[i], 'close'] = 110.0
        df.loc[df.index[i], 'high'] = 111.0
    df = detect_bos(df)
    # فقط یک BOS در کل DataFrame
    assert df['bullish_bos'].sum() == 1
