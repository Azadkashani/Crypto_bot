"""
تشخیص BOS (Break of Structure) پس از CHOCH.

BOS باید بعد از یک CHOCH هم‌جهت رخ دهد و فقط از کندل‌های بسته‌شده استفاده کند.
"""

import pandas as pd
import indicators
from choch import detect_choch


def detect_bos(df: pd.DataFrame, swing_left: int = None, swing_right: int = None) -> pd.DataFrame:
    """
    تشخیص نقاط BOS بر اساس شکست ساختار جدید پس از CHOCH.

    پارامترها:
        df: DataFrame شامل OHLCV و ایندکس زمانی UTC صعودی.
        swing_left, swing_right: پارامترهای تشخیص نوسان (پیش‌فرض از config).

    خروجی:
        DataFrame کپی‌شده با ستون‌های اضافی:
            - bullish_bos : True در کندلی که BOS صعودی رخ داده است.
            - bearish_bos : True در کندلی که BOS نزولی رخ داده است.
    """
    if swing_left is None:
        from config import SWING_LEFT_BARS
        swing_left = SWING_LEFT_BARS
    if swing_right is None:
        from config import SWING_RIGHT_BARS
        swing_right = SWING_RIGHT_BARS

    if 'swing_high' not in df.columns or 'swing_low' not in df.columns:
        df = indicators.detect_swings(df, left_bars=swing_left, right_bars=swing_right)
    if 'bullish_choch' not in df.columns or 'bearish_choch' not in df.columns:
        df = detect_choch(df, swing_left=swing_left, swing_right=swing_right)

    df = df.copy()
    df['bullish_bos'] = False
    df['bearish_bos'] = False

    active_direction = None  # 'bullish', 'bearish', یا None
    last_swing_high_idx = None
    last_swing_high_level = None
    last_swing_low_idx = None
    last_swing_low_level = None

    for idx in df.index:
        # ابتدا CHOCH را اعمال می‌کنیم
        if df.loc[idx, 'bullish_choch']:
            active_direction = 'bullish'
            last_swing_high_idx = None
            last_swing_high_level = None
            last_swing_low_idx = None
            last_swing_low_level = None

        if df.loc[idx, 'bearish_choch']:
            active_direction = 'bearish'
            last_swing_high_idx = None
            last_swing_high_level = None
            last_swing_low_idx = None
            last_swing_low_level = None

        # BOS را قبل از به‌روزرسانی نوسان جاری بررسی می‌کنیم
        if active_direction == 'bullish' and last_swing_high_idx is not None:
            # فقط close باید سطح را بشکند
            if df.loc[idx, 'close'] > last_swing_high_level:
                df.loc[idx, 'bullish_bos'] = True
                last_swing_high_idx = None
                last_swing_high_level = None
                continue  # کندل شکست را به‌عنوان نوسان جدید ثبت نمی‌کنیم

        if active_direction == 'bearish' and last_swing_low_idx is not None:
            # فقط close باید سطح را بشکند
            if df.loc[idx, 'close'] < last_swing_low_level:
                df.loc[idx, 'bearish_bos'] = True
                last_swing_low_idx = None
                last_swing_low_level = None
                continue

        # اگر BOS نبود، نوسان تأییدشده جاری را ذخیره می‌کنیم
        if df.loc[idx, 'swing_high']:
            last_swing_high_idx = idx
            last_swing_high_level = df.loc[idx, 'high']

        if df.loc[idx, 'swing_low']:
            last_swing_low_idx = idx
            last_swing_low_level = df.loc[idx, 'low']

    return df
