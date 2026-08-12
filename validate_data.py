#!/usr/bin/env python3
"""
اعتبارسنجی داده‌های واقعی از Gate.io Futures برای هر سه تایم‌فریم.
"""

from data import DataFetcher
from config import SYMBOL, TIMEFRAMES

def main():
    fetcher = DataFetcher()
    for tf in TIMEFRAMES:
        print(f"\n--- Timeframe: {tf} ---")
        try:
            # دریافت ۱۰ کندل آخر (بدون کش اجباری)
            df = fetcher.get_historical_data(
                symbol=SYMBOL,
                timeframe=tf,
                lookback_days=7,   # محدوده کوچک برای تست
                force_fetch=True,  # دریافت تازه از صرافی
                remove_incomplete_candle=True
            )
            if df.empty:
                print("No data received.")
                continue

            print(f"Number of candles: {len(df)}")
            print(f"First timestamp: {df.index[0]}")
            print(f"Last timestamp:  {df.index[-1]}")
            print("Latest OHLCV:")
            print(df.iloc[-1].to_string())
        except Exception as e:
            print(f"Error fetching {tf}: {e}")

if __name__ == "__main__":
    main()
