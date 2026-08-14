"""
دریافت و اعتبارسنجی داده‌های OHLCV تاریخی از Gate.io Futures.

این ماژول فقط خواندنی است و هیچ سفارشی ارسال نمی‌کند.
"""

from __future__ import annotations

import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List


def parse_timeframe(tf: str) -> timedelta:
    """تبدیل رشته تایم‌فریم به timedelta."""
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        raise ValueError(f"Unsupported timeframe: {tf}")


def expected_candles(start: pd.Timestamp, end: pd.Timestamp, timeframe: str) -> int:
    """تعداد کندل‌های مورد انتظار در بازه زمانی."""
    delta = parse_timeframe(timeframe)
    return int((end - start) / delta) + 1  # inclusive


def validate_ohlcv(
    df: pd.DataFrame,
    timeframe: str,
    expected_start: Optional[pd.Timestamp] = None,
    expected_end: Optional[pd.Timestamp] = None,
) -> Dict[str, Any]:
    """اعتبارسنجی کامل داده OHLCV."""
    issues = []
    if df.empty:
        issues.append("empty")
    else:
        if not df.index.is_monotonic_increasing:
            issues.append("unsorted timestamps")
        if df.index.duplicated().any():
            issues.append("duplicate timestamps")
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                issues.append(f"missing column {col}")
                continue
            if df[col].isnull().any():
                issues.append(f"NaN in {col}")
        if all(c in df.columns for c in ['open', 'high', 'low', 'close']):
            if (df['high'] < df[['open', 'close']].max(axis=1)).any():
                issues.append("high < max")
            if (df['low'] > df[['open', 'close']].min(axis=1)).any():
                issues.append("low > min")
        if 'volume' in df.columns and (df['volume'] < 0).any():
            issues.append("negative volume")
        if expected_start is not None and df.index.min() > expected_start:
            issues.append("missing leading candles")
        if expected_end is not None and df.index.max() < expected_end:
            issues.append("missing trailing candles")
        # آخرین کندل نباید ناقص باشد
        now = pd.Timestamp.now(tz='UTC')
        last_end = df.index[-1] + parse_timeframe(timeframe)
        if last_end > now:
            issues.append("incomplete last candle")
    return {"valid": len(issues) == 0, "issues": issues}


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

    df = pd.DataFrame(all_rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    df = df[~df.index.duplicated(keep='first')].sort_index()
    return df


class HistoricalDataDownloader:
    """دریافت‌کننده داده تاریخی برای یک Symbol و Timeframe خاص."""

    def __init__(self, exchange, symbol: str, timeframe: str, start: pd.Timestamp, end: pd.Timestamp):
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end

    def download(self) -> pd.DataFrame:
        since_ms = int(self.start.timestamp() * 1000)
        end_ms = int(self.end.timestamp() * 1000)
        df = fetch_ohlcv_paginated(self.exchange, self.symbol, self.timeframe, since_ms, end_ms)
        if not df.empty:
            df = df.loc[(df.index >= self.start) & (df.index <= self.end)]
        return df

    def save(self, df: pd.DataFrame, data_dir: str) -> str:
        os.makedirs(data_dir, exist_ok=True)
        safe = self.symbol.replace('/', '_').replace(':', '_')
        path = os.path.join(data_dir, f"{safe}_{self.timeframe}.csv")
        df.to_csv(path)
        return path
