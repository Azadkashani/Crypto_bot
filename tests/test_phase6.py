import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import indicators
from choch import detect_choch
from bos import detect_bos


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
    """ساختار نزولی، CHOCH صعودی، نوسان بالای جدید، سپس BOS صعودی."""
    df = _make_base_df(40)

    # نوسان بالای اول در ایندکس 10
    for i in range(7, 14):
        if i == 10:
            df.loc[df.index[10], 'high'] = 110
            df.loc[df.index[10], 'low'] = 105
            df.loc[df.index[10], 'close'] = 106
            df.loc[df.index[10], 'open'] = 105.5
        else:
            val = 100 + abs(i - 10) * 0.5
            df.loc[df.index[i], 'high'] = val
            df.loc[df.index[i], 'low'] = val - 2
            df.loc[df.index[i], 'close'] = val - 1
            df.loc[df.index[i], 'open'] = val - 1.5

    # نوسان بالای دوم (Lower High) در ایندکس 20
    for i in range(17, 24):
        if i == 20:
            df.loc[df.index[20], 'high'] = 105
            df.loc[df.index[20], 'low'] = 101
            df.loc[df.index[20], 'close'] = 102
            df.loc[df.index[20], 'open'] = 101.5
        else:
            val = 100 + abs(i - 20) * 0.3
            df.loc[df.index[i], 'high'] = val
            df.loc[df.index[i], 'low'] = val - 2
            df.loc[df.index[i], 'close'] = val - 1
            df.loc[df.index[i], 'open'] = val - 1.5

    # کندل CHOCH صعودی در 25
    df.loc[df.index[25], 'open'] = 104
    df.loc[df.index[25], 'high'] = 107
    df.loc[df.index[25], 'low'] = 103
    df.loc[df.index[25], 'close'] = 106  # بالای Lower High قبلی

    # شروع ساختار صعودی پس از CHOCH
    for i in range(26, 28):
        df.loc[df.index[i], 'open'] = 104.5
        df.loc[df.index[i], 'high'] = 106
        df.loc[df.index[i], 'low'] = 104
        df.loc[df.index[i], 'close'] = 105

    # نوسان بالای جدید (برای BOS) در 28
    df.loc[df.index[28], 'open'] = 105
    df.loc[df.index[28], 'high'] = 108
    df.loc[df.index[28], 'low'] = 104
    df.loc[df.index[28], 'close'] = 105

    # کندل‌های تأیید نوسان (باید high کمتر از 108 باشند)
    levels = [107.5, 107.0, 106.5]
    for i, val in zip(range(29, 32), levels):
        df.loc[df.index[i], 'open'] = val - 1.0
        df.loc[df.index[i], 'high'] = val
        df.loc[df.index[i], 'low'] = val - 1.5
        df.loc[df.index[i], 'close'] = val - 0.5

    # کندل BOS صعودی در 32: بسته بالای 108
    df.loc[df.index[32], 'open'] = 107.5
    df.loc[df.index[32], 'high'] = 110
    df.loc[df.index[32], 'low'] = 106
    df.loc[df.index[32], 'close'] = 109

    # بقیه کندل‌ها
    for i in range(33, 40):
        val = 109.5 + (i - 33) * 0.1
        df.loc[df.index[i], 'open'] = val - 0.3
        df.loc[df.index[i], 'high'] = val
        df.loc[df.index[i], 'low'] = val - 1
        df.loc[df.index[i], 'close'] = val - 0.5

    return df


def _make_bearish_choch_then_bos():
    """ساختار صعودی، CHOCH نزولی، نوسان پایین جدید، سپس BOS نزولی."""
    df = _make_base_df(40)

    # نوسان پایین اول در ایندکس 10
    for i in range(7, 14):
        if i == 10:
            df.loc[df.index[10], 'low'] = 90
            df.loc[df.index[10], 'high'] = 95
            df.loc[df.index[10], 'close'] = 94
            df.loc[df.index[10], 'open'] = 94.5
        else:
            val = 100 - abs(i - 10) * 0.5
            df.loc[df.index[i], 'low'] = val
            df.loc[df.index[i], 'high'] = val + 2
            df.loc[df.index[i], 'close'] = val + 1
            df.loc[df.index[i], 'open'] = val + 1.5

    # نوسان پایین دوم (Higher Low) در 20
    for i in range(17, 24):
        if i == 20:
            df.loc[df.index[20], 'low'] = 95
            df.loc[df.index[20], 'high'] = 99
            df.loc[df.index[20], 'close'] = 98
            df.loc[df.index[20], 'open'] = 98.5
        else:
            val = 100 - abs(i - 20) * 0.3
            df.loc[df.index[i], 'low'] = val
            df.loc[df.index[i], 'high'] = val + 2
            df.loc[df.index[i], 'close'] = val + 1
            df.loc[df.index[i], 'open'] = val + 1.5

    # کندل CHOCH نزولی در 25
    df.loc[df.index[25], 'open'] = 97
    df.loc[df.index[25], 'high'] = 98
    df.loc[df.index[25], 'low'] = 93
    df.loc[df.index[25], 'close'] = 94  # زیر Higher Low قبلی

    # شروع ساختار نزولی پس از CHOCH
    for i in range(26, 28):
        df.loc[df.index[i], 'open'] = 97.5
        df.loc[df.index[i], 'high'] = 98
        df.loc[df.index[i], 'low'] = 96
        df.loc[df.index[i], 'close'] = 97

    # نوسان پایین جدید (برای BOS) در 28
    df.loc[df.index[28], 'open'] = 95.5
    df.loc[df.index[28], 'high'] = 96
    df.loc[df.index[28], 'low'] = 92
    df.loc[df.index[28], 'close'] = 95

    # کندل‌های تأیید نوسان (low باید بیشتر از 92 باشد)
    levels = [93.0, 93.5, 94.0]
    for i, val in zip(range(29, 32), levels):
        df.loc[df.index[i], 'open'] = val + 0.5
        df.loc[df.index[i], 'high'] = val + 1.5
        df.loc[df.index[i], 'low'] = val
        df.loc[df.index[i], 'close'] = val + 1.0

    # کندل BOS نزولی در 32: بسته زیر 92
    df.loc[df.index[32], 'open'] = 94
    df.loc[df.index[32], 'high'] = 95
    df.loc[df.index[32], 'low'] = 90
    df.loc[df.index[32], 'close'] = 91

    # بقیه کندل‌ها
    for i in range(33, 40):
        val = 91.5 - (i - 33) * 0.1
        df.loc[df.index[i], 'open'] = val + 0.3
        df.loc[df.index[i], 'high'] = val + 1
        df.loc[df.index[i], 'low'] = val - 0.5
        df.loc[df.index[i], 'close'] = val

    return df


# -------------------------------
# تست‌ها
# -------------------------------
def test_bullish_bos_detected():
    df = _make_bullish_choch_then_bos()
    df = detect_bos(df)
    assert df.loc[df.index[32], 'bullish_bos'] == True
    assert df['bearish_bos'].sum() == 0


def test_bearish_bos_detected():
    df = _make_bearish_choch_then_bos()
    df = detect_bos(df)
    assert df.loc[df.index[32], 'bearish_bos'] == True
    assert df['bullish_bos'].sum() == 0


def test_choch_is_not_bos():
    df = _make_bullish_choch_then_bos()
    partial = df.iloc[:26]  # فقط تا کندل CHOCH
    partial = detect_bos(partial)
    assert partial.loc[partial.index[25], 'bullish_bos'] == False
    assert partial['bullish_bos'].sum() == 0


def test_wick_only_break_does_not_trigger_bos():
    df = _make_bullish_choch_then_bos()
    # سایه بالا از 108 عبور می‌کند اما کلوز زیر 108 است
    df.loc[df.index[32], 'high'] = 109.5
    df.loc[df.index[32], 'close'] = 107.5

    # فقط تا خود کندل 32 پردازش می‌کنیم تا کندل‌های بعدی نتوانند BOS ایجاد کنند
    partial = df.iloc[:33]

    partial = detect_bos(partial)
    assert partial.loc[partial.index[32], 'bullish_bos'] == False
    assert partial['bullish_bos'].sum() == 0


def test_incomplete_candle_does_not_trigger_bos():
    df = _make_bullish_choch_then_bos()
    partial = df.iloc[:32]  # قبل از کندل BOS
    partial = detect_bos(partial)
    assert partial['bullish_bos'].sum() == 0


def test_no_lookahead():
    df = _make_bullish_choch_then_bos()
    full = detect_bos(df)
    assert full.loc[full.index[32], 'bullish_bos'] == True

    partial = df.iloc[:33]
    partial_detected = detect_bos(partial)
    assert partial_detected.loc[partial.index[32], 'bullish_bos'] == True
    assert full['bullish_bos'].sum() == 1  # فقط یک BOS


def test_direction_correctness():
    bull_df = detect_bos(_make_bullish_choch_then_bos())
    bear_df = detect_bos(_make_bearish_choch_then_bos())
    assert bull_df['bearish_bos'].sum() == 0
    assert bear_df['bullish_bos'].sum() == 0


def test_duplicate_prevention():
    df = _make_bullish_choch_then_bos()
    # بعد از BOS، چند کندل دیگر هم بالای سطح 108 می‌مانند
    for i in range(33, 40):
        df.loc[df.index[i], 'close'] = 110.0
        df.loc[df.index[i], 'high'] = 111.0
    df = detect_bos(df)
    assert df['bullish_bos'].sum() == 1
