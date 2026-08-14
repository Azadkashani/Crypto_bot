"""
ماژول دریافت و اعتبارسنجی داده‌های تاریخی Gate.io Futures.
"""

from __future__ import annotations

import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

import ccxt


class DataCoverageError(Exception):
    """خطای ناشی از پوشش ناکافی داده تاریخی."""
    pass


def timeframe_to_timedelta(tf: str) -> timedelta:
    """تبدیل رشته تایم‌فریم به timedelta."""
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    raise ValueError(f"Unsupported timeframe: {tf}")


def parse_timeframe(tf: str) -> timedelta:
    """نام دوم برای timeframe_to_timedelta."""
    return timeframe_to_timedelta(tf)


def expected_candles(start: pd.Timestamp, end: pd.Timestamp, timeframe: str) -> int:
    """تعداد کندل‌های مورد انتظار در بازه زمانی."""
    delta = timeframe_to_timedelta(timeframe)
    return int((end - start) / delta) + 1


def validate_ohlcv(df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    """
    اعتبارسنجی ساختار و کیفیت داده OHLCV.

    خروجی دیکشنری شامل valid و issues است.
    """
    issues = []
    if df.empty:
        issues.append("empty")
        return {"valid": False, "issues": issues}

    if not df.index.is_monotonic_increasing:
        issues.append("unsorted timestamps")

    if df.index.duplicated().any():
        issues.append("duplicate timestamps")

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            issues.append(f"missing column {col}")
            continue
        if df[col].isnull().any():
            issues.append(f"NaN in {col}")

    if all(c in df.columns for c in ["open", "high", "low", "close"]):
        if (df["high"] < df[["open", "close"]].max(axis=1)).any():
            issues.append("high < max")
        if (df["low"] > df[["open", "close"]].min(axis=1)).any():
            issues.append("low > min")
        if (df["high"] < df["low"]).any():
            issues.append("high < low")

    if "volume" in df.columns and (df["volume"] < 0).any():
        issues.append("negative volume")

    # بررسی آخرین کندل ناقص
    delta = timeframe_to_timedelta(timeframe)
    now = pd.Timestamp.now(tz="UTC")

    if df.index.tz is None:
        # اگر ایندکس timezone نداشت، بدون تبدیل to UTC، فقط بررسی ناقص بودن را رد می‌کنیم
        # تا از TypeError جلوگیری شود
        pass
    else:
        last_end = df.index[-1] + delta
        if last_end > now:
            issues.append("incomplete last candle")

    return {"valid": len(issues) == 0, "issues": issues}


def validate_coverage(
    df: pd.DataFrame,
    timeframe: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    major_gap_ratio: float = 5.0,
) -> Dict[str, Any]:
    """
    بررسی پوشش کامل بازه [start, end].

    فقط داده‌های داخل [start, end] برای بررسی گپ و پوشش در نظر گرفته می‌شوند.
    داده‌های خارج از این بازه (warm-up) نقشی ندارند.
    """
    if df.empty:
        return {
            "coverage_ok": False,
            "first": None,
            "last": None,
            "rows": 0,
            "gaps": 0,
            "major_gaps": [],
            "reason": "empty",
        }

    # فقط بازه موردنظر
    mask = (df.index >= start) & (df.index <= end)
    df_slice = df.loc[mask]

    if df_slice.empty:
        return {
            "coverage_ok": False,
            "first": None,
            "last": None,
            "rows": 0,
            "gaps": 0,
            "major_gaps": [],
            "reason": f"no data in requested range [{start} → {end}]",
        }

    first = df_slice.index.min()
    last = df_slice.index.max()
    rows = len(df_slice)

    # بررسی اینکه ابتدای بازه پوشش داده شده باشد
    if first > start:
        return {
            "coverage_ok": False,
            "first": first,
            "last": last,
            "rows": rows,
            "gaps": 0,
            "major_gaps": [],
            "reason": f"missing leading data: first {first} > start {start}",
        }

    if last < end:
        return {
            "coverage_ok": False,
            "first": first,
            "last": last,
            "rows": rows,
            "gaps": 0,
            "major_gaps": [],
            "reason": f"missing trailing data: last {last} < end {end}",
        }

    delta = timeframe_to_timedelta(timeframe)
    diffs = df_slice.index.to_series().diff().dt.total_seconds()
    expected_sec = delta.total_seconds()
    gap_mask = diffs > expected_sec * major_gap_ratio
    major_gaps = df_slice.index[gap_mask].tolist()

    return {
        "coverage_ok": len(major_gaps) == 0,
        "first": first,
        "last": last,
        "rows": rows,
        "gaps": int(gap_mask.sum()),
        "major_gaps": major_gaps,
        "reason": "OK" if len(major_gaps) == 0 else f"major gaps at {major_gaps[:5]}",
    }
