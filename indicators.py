"""
اندیکاتورهای تکنیکال پایه و تشخیص سویینگ.
تمامی محاسبات بر اساس داده‌های تاریخی (بدون نگاه به آینده) انجام می‌شود.
"""

import pandas as pd
import numpy as np


def add_ema(df: pd.DataFrame, period: int, src_col: str = 'close', col_name: str = None) -> pd.DataFrame:
    """محاسبه EMA روی ستون مشخص و افزودن به DataFrame."""
    if col_name is None:
        col_name = f'ema_{period}'
    result = df.copy()
    result[col_name] = result[src_col].ewm(span=period, adjust=False).mean()
    return result


def add_rsi(df: pd.DataFrame, period: int = 14, src_col: str = 'close', col_name: str = None) -> pd.DataFrame:
    """محاسبه RSI و افزودن به DataFrame."""
    if col_name is None:
        col_name = f'rsi_{period}'
    result = df.copy()
    delta = result[src_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    result[col_name] = 100.0 - (100.0 / (1.0 + rs))
    return result


def add_atr(df: pd.DataFrame, period: int = 14, col_name: str = None) -> pd.DataFrame:
    """محاسبه ATR و افزودن به DataFrame."""
    if col_name is None:
        col_name = f'atr_{period}'
    result = df.copy()
    high, low, close = result['high'], result['low'], result['close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    result[col_name] = tr.ewm(alpha=1/period, adjust=False).mean()
    return result


def add_adx(df: pd.DataFrame, period: int = 14, col_name: str = None) -> pd.DataFrame:
    """محاسبه ADX و افزودن به DataFrame."""
    if col_name is None:
        col_name = f'adx_{period}'
    result = df.copy()
    high, low, close = result['high'], result['low'], result['close']
    prev_close = close.shift()
    up_move = high - high.shift()
    down_move = low.shift() - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr_series = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / atr_series
    minus_di = 100.0 * pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / atr_series
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100.0
    result[col_name] = dx.ewm(alpha=1/period, adjust=False).mean()
    return result


def add_volume_sma(df: pd.DataFrame, period: int = 20, col_name: str = None) -> pd.DataFrame:
    """محاسبه میانگین ساده حجم و افزودن به DataFrame."""
    if col_name is None:
        col_name = f'volume_sma_{period}'
    result = df.copy()
    result[col_name] = result['volume'].rolling(window=period).mean()
    return result


def detect_swings(df: pd.DataFrame, left_bars: int = 3, right_bars: int = 3) -> pd.DataFrame:
    """
    تشخیص نقاط سویینگ (Swing High و Swing Low) با تأخیر تأیید (بدون نگاه به آینده).

    پارامترها:
        df: DataFrame شامل ستون‌های 'high' و 'low'.
        left_bars: تعداد کندل‌های سمت چپ برای بررسی قله/دره.
        right_bars: تعداد کندل‌های سمت راست که باید برای تأیید صبر کرد.

    خروجی:
        DataFrame کپی‌شده با ستون‌های اضافی:
        - 'swing_high': بولین، True اگر کندل یک Swing High تأییدشده باشد.
        - 'swing_low': بولین، True اگر کندل یک Swing Low تأییدشده باشد.

    نکته: یک سویینگ تنها زمانی در ایندکس i تأیید می‌شود که i + right_bars < len(df)
    و مقادیر high/low در i با تمام کندل‌های [i-left_bars ... i+right_bars] مقایسه شوند.
    بنابراین از کندل‌های آینده برای تأیید استفاده نمی‌کند؛ صرفاً اعلام آن به تعویق می‌افتد.
    """
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)

    swing_high = np.zeros(n, dtype=bool)
    swing_low = np.zeros(n, dtype=bool)

    for i in range(left_bars, n - right_bars):
        window_highs = highs[i - left_bars : i + right_bars + 1]
        window_lows = lows[i - left_bars : i + right_bars + 1]
        if highs[i] == window_highs.max() and list(window_highs).count(highs[i]) == 1:
            swing_high[i] = True
        if lows[i] == window_lows.min() and list(window_lows).count(lows[i]) == 1:
            swing_low[i] = True

    df['swing_high'] = swing_high
    df['swing_low'] = swing_low
    return df
