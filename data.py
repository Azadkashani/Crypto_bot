"""
ماژول مدیریت داده‌های تاریخی و زنده از Gate.io Futures.
هر تایم‌فریم مستقل دریافت و ذخیره می‌شود.
"""

import os
import pandas as pd
import ccxt
from datetime import datetime, timezone
from config import (
    EXCHANGE_ID, EXCHANGE_OPTIONS, SYMBOL, TIMEFRAMES, DATA_DIR
)


class DataFetcher:
    """
    دریافت‌کننده داده از صرافی و مدیریت کش محلی.
    """
    def __init__(self):
        self.exchange = ccxt.gateio(EXCHANGE_OPTIONS)
        self.exchange.load_markets()
        # اطمینان از وجود پوشه دیتا
        os.makedirs(DATA_DIR, exist_ok=True)

    def fetch_ohlcv(
        self,
        symbol: str = SYMBOL,
        timeframe: str = '5m',
        since: int = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        دریافت داده‌های OHLCV از صرافی و بازگرداندن DataFrame تمیز.
        """
        raw = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        df = pd.DataFrame(
            raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        # تبدیل به نوع عددی
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _file_path(self, symbol: str, timeframe: str) -> str:
        """
        مسیر فایل CSV برای یک جفت نماد و تایم‌فریم.
        """
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        return os.path.join(DATA_DIR, f"{safe_symbol}_{timeframe}.csv")

    def save_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """ذخیره DataFrame در فایل CSV."""
        path = self._file_path(symbol, timeframe)
        df.to_csv(path)
        print(f"Data saved: {path}")

    def load_data(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """بارگذاری داده از فایل محلی. اگر فایل وجود نداشت، None برمی‌گرداند."""
        path = self._file_path(symbol, timeframe)
        if os.path.exists(path):
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True)
            return df
        return None

    def get_historical_data(
        self,
        symbol: str = SYMBOL,
        timeframe: str = '5m',
        lookback_days: int = 30,
        force_fetch: bool = False
    ) -> pd.DataFrame:
        """
        دریافت داده تاریخی:
        - ابتدا از فایل محلی می‌خواند.
        - اگر کافی نبود یا force_fetch فعال بود، از صرافی دریافت و ذخیره می‌کند.
        """
        df = self.load_data(symbol, timeframe) if not force_fetch else None

        # تاریخ سررسید برای داده‌های موردنیاز
        now = datetime.now(timezone.utc)
        since_date = now - pd.Timedelta(days=lookback_days)

        if df is not None and not df.empty:
            last_date = df.index[-1]
            if last_date >= since_date:
                # داده کافی است
                return df.loc[df.index >= since_date].copy()

        # دریافت داده جدید
        since_ts = int(since_date.timestamp() * 1000)
        new_df = self.fetch_ohlcv(symbol, timeframe, since=since_ts, limit=1000)

        # اگر داده محلی وجود داشت، ادغام کن
        if df is not None:
            combined = pd.concat([df, new_df])
            combined = combined[~combined.index.duplicated(keep='last')]
            combined.sort_index(inplace=True)
        else:
            combined = new_df

        # ذخیره ترکیب نهایی
        self.save_data(combined, symbol, timeframe)
        return combined.loc[combined.index >= since_date].copy()


# یک نمونه سراسری برای استفاده در سایر ماژول‌ها (اختیاری)
fetcher = DataFetcher()
