"""
تشخیص CHOCH (Change of Character) بر اساس ساختار نوسانی تأییدشده.

این ماژول فقط تشخیص تغییر کاراکتر را انجام می‌دهد و مستقل از RSI و BOS است.
"""

import pandas as pd
import indicators


def detect_choch(df: pd.DataFrame, swing_left: int = None, swing_right: int = None) -> pd.DataFrame:
    """
    تشخیص نقاط CHOCH بر اساس شکست آخرین نوسان تأییدشده در خلاف جهت روند کوتاه‌مدت.

    تعریف:
        - Bullish CHOCH: در یک روند نزولی کوتاه‌مدت (Lower Highs)، آخرین سقف پایین‌تر
          با بسته شدن کندل بالای سطح آن شکسته می‌شود.
        - Bearish CHOCH: در یک روند صعودی کوتاه‌مدت (Higher Lows)، آخرین کف بالاتر
          با بسته شدن کندل زیر سطح آن شکسته می‌شود.

    فقط از کندل‌های بسته‌شده استفاده می‌کند و هیچ نگاه به آینده‌ای ندارد.

    پارامترها:
        df: DataFrame شامل ستون‌های OHLCV و ایندکس زمانی UTC صعودی.
        swing_left: (اختیاری) تعداد کندل‌های چپ برای تشخیص نوسان.
        swing_right: (اختیاری) تعداد کندل‌های راست برای تأیید نوسان.

    خروجی:
        DataFrame کپی‌شده با دو ستون اضافی:
            - bullish_choch : True فقط در کندلی که شکست صعودی رخ داده است.
            - bearish_choch : True فقط در کندلی که شکست نزولی رخ داده است.
    """
    if swing_left is None:
        from config import SWING_LEFT_BARS
        swing_left = SWING_LEFT_BARS
    if swing_right is None:
        from config import SWING_RIGHT_BARS
        swing_right = SWING_RIGHT_BARS

    # اطمینان از وجود ستون‌های نوسان
    if 'swing_high' not in df.columns or 'swing_low' not in df.columns:
        df = indicators.detect_swings(df, left_bars=swing_left, right_bars=swing_right)

    df = df.copy()

    # ستون‌های خروجی
    df['bullish_choch'] = False
    df['bearish_choch'] = False

    # اندیس‌های نوسان‌های تأییدشده
    swing_high_indices = df.index[df['swing_high']].tolist()
    swing_low_indices = df.index[df['swing_low']].tolist()

    # وضعیت فعال جهت ساختار تا از تکرار CHOCH جلوگیری شود
    active_direction = None  # None, 'bullish', 'bearish'

    for idx in df.index:
        # ---------- Bullish CHOCH ----------
        # فقط زمانی بررسی می‌شود که در رژیم صعودی ناشی از CHOCH قبلی نباشیم
        if active_direction != 'bullish':
            prior_highs = [h for h in swing_high_indices if h < idx]
            if len(prior_highs) >= 2:
                recent_high = prior_highs[-1]
                previous_high = prior_highs[-2]
                recent_level = df.loc[recent_high, 'high']
                previous_level = df.loc[previous_high, 'high']
                if recent_level < previous_level:
                    # شکست با بسته شدن بالای سطح سقف اخیر
                    if df.loc[idx, 'close'] > recent_level:
                        df.loc[idx, 'bullish_choch'] = True
                        active_direction = 'bullish'
                        continue  # در این کندل دیگر bearish بررسی نمی‌شود

        # ---------- Bearish CHOCH ----------
        # فقط زمانی بررسی می‌شود که در رژیم نزولی ناشی از CHOCH قبلی نباشیم
        if active_direction != 'bearish':
            prior_lows = [l for l in swing_low_indices if l < idx]
            if len(prior_lows) >= 2:
                recent_low = prior_lows[-1]
                previous_low = prior_lows[-2]
                recent_level = df.loc[recent_low, 'low']
                previous_level = df.loc[previous_low, 'low']
                if recent_level > previous_level:
                    # شکست با بسته شدن زیر سطح کف اخیر
                    if df.loc[idx, 'close'] < recent_level:
                        df.loc[idx, 'bearish_choch'] = True
                        active_direction = 'bearish'
                        continue  # در این کندل دیگر bullish بررسی نمی‌شود

    return df
