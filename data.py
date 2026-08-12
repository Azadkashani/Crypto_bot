"""
ماژول مدیریت داده‌های تاریخی و زنده از Gate.io Futures.
هر تایم‌فریم مستقل دریافت و ذخیره می‌شود.
"""

import os
import pandas as pd
import ccxt
from datetime import datetime, timezone, timedelta
from config import (
    EXCHANGE_ID, EXCHANGE_OPTIONS, SYMBOL, TIMEFRAMES, DATA_DIR
)


class DataFetcher:
    """
    دریافت‌کننده داده از صرافی و مدیریت کش محلی.
    """

    def __init__(self):
        self.exchange = ccxt.gate(EXCHANGE_OPTIONS)
        self.exchange.load_markets()
        os.makedirs(DATA_DIR, exist_ok=True)

    def _timeframe_to_timedelta(self, timeframe: str) -> timedelta:
        """تبدیل رشته تایم‌فریم به timedelta."""
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        if unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def fetch_ohlcv(
        self,
        symbol: str = SYMBOL,
        timeframe: str = '5m',
        since: int = None,
        limit: int = 1000,
        remove_incomplete_candle: bool = False
    ) -> pd.DataFrame:
        """
        دریافت داده‌های OHLCV از صرافی و بازگرداندن DataFrame تمیز.
        اگر remove_incomplete_candle=True باشد، آخرین کندل ناقص حذف می‌شود.
        """
        raw = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        df = pd.DataFrame(
            raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # حذف کندل ناقص در صورت درخواست
        if remove_incomplete_candle and not df.empty:
            delta = self._timeframe_to_timedelta(timeframe)
            now = datetime.now(timezone.utc)
            last_candle_end = df.index[-1] + delta
            if last_candle_end > now:
                df = df.iloc[:-1]

        return df

    def _file_path(self, symbol: str, timeframe: str) -> str:
        """مسیر فایل CSV برای یک جفت نماد و تایم‌فریم."""
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        return os.path.join(DATA_DIR, f"{safe_symbol}_{timeframe}.csv")

    def save_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """ذخیره DataFrame در فایل CSV."""
        path = self._file_path(symbol, timeframe)
        df.to_csv(path)
        print(f"Data saved: {path}")

    def load_data(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """بارگذاری داده از فایل محلی. همیشه به‌صورت صعودی مرتب می‌شود."""
        path = self._file_path(symbol, timeframe)
        if os.path.exists(path):
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True)
            df.sort_index(inplace=True)  # تضمین ترتیب صعودی
            return df
        return None

    def get_historical_data(
        self,
        symbol: str = SYMBOL,
        timeframe: str = '5m',
        lookback_days: int = 30,
        force_fetch: bool = False,
        remove_incomplete_candle: bool = True
    ) -> pd.DataFrame:
        """
        دریافت داده تاریخی.
        به‌طور پیش‌فرض کندل‌های ناقص حذف می‌شوند.
        """
        df = self.load_data(symbol, timeframe) if not force_fetch else None

        now = datetime.now(timezone.utc)
        since_date = now - pd.Timedelta(days=lookback_days)

        if df is not None and not df.empty:
            last_date = df.index[-1]
            if last_date >= since_date:
                return df.loc[df.index >= since_date].copy()

        since_ts = int(since_date.timestamp() * 1000)
        new_df = self.fetch_ohlcv(
            symbol, timeframe, since=since_ts, limit=1000,
            remove_incomplete_candle=remove_incomplete_candle
        )

        if df is not None:
            combined = pd.concat([df, new_df])
            combined = combined[~combined.index.duplicated(keep='last')]
            combined.sort_index(inplace=True)
        else:
            combined = new_df

        self.save_data(combined, symbol, timeframe)
        return combined.loc[combined.index >= since_date].copy()
