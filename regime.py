"""
تشخیص رژیم بازار بر اساس EMA، موقعیت قیمت و ADX.
هر دیتافریم مستقل پردازش می‌شود.
"""

import pandas as pd
from indicators import add_ema, add_adx
import config

REGIME_BULLISH = "BULLISH"
REGIME_BEARISH = "BEARISH"
REGIME_RANGE = "RANGE"

def get_regime(df: pd.DataFrame) -> str:
    """
    تشخیص رژیم بازار برای آخرین کندل بسته‌شده در DataFrame.

    پارامترها:
        df: DataFrame شامل ستون‌های OHLCV با ایندکس UTC صعودی.

    خروجی:
        یکی از مقادیر REGIME_BULLISH، REGIME_BEARISH یا REGIME_RANGE.
    """
    if df.empty:
        return REGIME_RANGE

    # کپی برای جلوگیری از تغییر DataFrame اصلی
    df_enriched = df.copy()

    # محاسبه EMA ها
    df_enriched = add_ema(df_enriched, period=config.EMA_FAST, src_col='close', col_name='ema_fast')
    df_enriched = add_ema(df_enriched, period=config.EMA_MID, src_col='close', col_name='ema_mid')
    df_enriched = add_ema(df_enriched, period=config.EMA_SLOW, src_col='close', col_name='ema_slow')

    # محاسبه ADX
    df_enriched = add_adx(df_enriched, period=config.ADX_PERIOD, col_name='adx')

    last = df_enriched.iloc[-1]
    ema_fast = last['ema_fast']
    ema_mid = last['ema_mid']
    ema_slow = last['ema_slow']
    close = last['close']
    adx = last['adx']

    # اگر هر مقداری NaN باشد، رژیم RANGE در نظر گرفته می‌شود
    if pd.isna(ema_fast) or pd.isna(ema_mid) or pd.isna(ema_slow) or pd.isna(adx):
        return REGIME_RANGE

    bullish_structure = ema_fast > ema_mid > ema_slow
    bearish_structure = ema_fast < ema_mid < ema_slow
    close_above_ema_fast = close > ema_fast
    close_below_ema_fast = close < ema_fast
    trend_filter = adx >= config.ADX_MIN_TREND

    if bullish_structure and close_above_ema_fast and trend_filter:
        return REGIME_BULLISH
    elif bearish_structure and close_below_ema_fast and trend_filter:
        return REGIME_BEARISH
    else:
        return REGIME_RANGE

def regimes_aligned(regime_4h: str, regime_1h: str) -> str:
    """
    بررسی هم‌راستایی رژیم‌ها.

    خروجی:
        'aligned_bullish' : هر دو صعودی
        'aligned_bearish' : هر دو نزولی
        'not_aligned'     : سایر ترکیب‌ها
    """
    if regime_4h == REGIME_BULLISH and regime_1h == REGIME_BULLISH:
        return "aligned_bullish"
    elif regime_4h == REGIME_BEARISH and regime_1h == REGIME_BEARISH:
        return "aligned_bearish"
    else:
        return "not_aligned"
