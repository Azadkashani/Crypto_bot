"""
ماژول دریافت و اعتبارسنجی داده‌های تاریخی Gate.io Futures.

این ماژول:
    - داده‌های 5m / 1h / 4h را با رعایت محدودیت‌های صرافی دانلود می‌کند.
    - اعتبارسنجی کامل داده (ترتیب، تکراری نبودن، OHLCV معتبر) انجام می‌دهد.
    - پوشش بازه تاریخی را بررسی می‌کند و در صورت ناقص بودن، خطا می‌دهد.
    - داده‌های محلی را فقط در صورتی معتبر می‌داند که پوشش کافی داشته باشند.
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

    if df.index.tz is not None:
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


def build_dataframe(rows: list) -> pd.DataFrame:
    """ساخت DataFrame از ردیف‌های خام ccxt."""
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()
    return df


def fetch_ohlcv_paginated(
    exchange,
    symbol: str,
    timeframe: str,
    since_ms: int,
    end_ms: Optional[int] = None,
) -> pd.DataFrame:
    """دریافت کامل OHLCV با استفاده از pagination."""
    all_rows = []
    current_since = since_ms
    while True:
        if end_ms is not None and current_since >= end_ms:
            break
        limit = 1000
        raw = exchange.exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
        if not raw:
            break
        all_rows.extend(raw)
        last_ts = raw[-1][0]
        if last_ts <= current_since:
            break
        current_since = last_ts + 1
        if len(raw) < limit:
            break

    if not all_rows:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    return build_dataframe(all_rows)


class HistoricalDataDownloader:
    """دریافت‌کننده داده تاریخی برای یک Symbol و Timeframe خاص."""

    def __init__(
        self,
        exchange,
        symbol: str,
        timeframe: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        max_points: int = 1000,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end
        self.max_points = max_points

    def _delta_ms(self) -> int:
        delta = timeframe_to_timedelta(self.timeframe)
        return int(delta.total_seconds() * 1000)

    def download(self) -> pd.DataFrame:
        """دانلود کامل داده از start تا end با pagination."""
        if self.start >= self.end:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        start_ms = int(self.start.timestamp() * 1000)
        end_ms = int(self.end.timestamp() * 1000)
        delta_ms = self._delta_ms()

        if delta_ms <= 0:
            raise ValueError(f"Invalid timeframe: {self.timeframe}")

        all_rows: List[list] = []
        cursor = start_ms
        while cursor <= end_ms:
            remaining_points = max(1, int((end_ms - cursor) / delta_ms) + 1)
            limit = min(self.max_points, remaining_points)

            try:
                raw = self.exchange.exchange.fetch_ohlcv(
                    self.symbol,
                    self.timeframe,
                    since=cursor,
                    limit=limit,
                )
            except ccxt.BadRequest as e:
                raise DataCoverageError(
                    f"Gate.io historical data unavailable for {self.symbol} "
                    f"{self.timeframe} at {pd.Timestamp(cursor, unit='ms', tz='UTC')}: {e}"
                )
            except Exception as e:
                raise DataCoverageError(
                    f"Gate.io fetch failed for {self.symbol} {self.timeframe}: {e}"
                )

            if not raw:
                break

            all_rows.extend(raw)
            last_ts = raw[-1][0]

            if last_ts <= cursor:
                break

            cursor = last_ts + delta_ms

        df = build_dataframe(all_rows)

        if df.empty:
            raise DataCoverageError(
                f"No historical data returned for {self.symbol} {self.timeframe} "
                f"from {self.start} to {self.end}"
            )

        # محدود کردن به بازه درخواستی
        df = df.loc[(df.index >= self.start) & (df.index <= self.end)]

        coverage = validate_coverage(df, self.timeframe, self.start, self.end)
        if not coverage["coverage_ok"]:
            raise DataCoverageError(
                f"Historical data coverage insufficient for {self.symbol} {self.timeframe}: "
                f"{coverage['reason']}. Requested {self.start} → {self.end}, "
                f"actual {coverage['first']} → {coverage['last']}"
            )

        return df

    def save(self, df: pd.DataFrame, data_dir: str) -> str:
        """ذخیره DataFrame در فایل CSV."""
        os.makedirs(data_dir, exist_ok=True)
        safe = self.symbol.replace("/", "_").replace(":", "_")
        path = os.path.join(data_dir, f"{safe}_{self.timeframe}.csv")
        df.to_csv(path)
        return path


def load_local_csv(symbol: str, timeframe: str, data_dir: str) -> Optional[pd.DataFrame]:
    """خواندن فایل CSV محلی در صورت وجود."""
    safe = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(data_dir, f"{safe}_{timeframe}.csv")
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def save_csv(df: pd.DataFrame, symbol: str, timeframe: str, data_dir: str) -> str:
    """ذخیره DataFrame در CSV."""
    os.makedirs(data_dir, exist_ok=True)
    safe = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(data_dir, f"{safe}_{timeframe}.csv")
    df.to_csv(path)
    return path
