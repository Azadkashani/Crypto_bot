#!/usr/bin/env python3
"""
اجرای تحلیل شکست معاملات SL روی داده‌های موجود.

این اسکریپت:
    - داده‌های تاریخی را از CSV محلی می‌خواند.
    - یک Backtest را با OptimizedBacktestRunner اجرا می‌کند.
    - معاملات SL را تحلیل می‌کند.
    - گزارش کنسول و CSV تولید می‌کند.
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from gate_exchange import GateExchange
from historical_data import load_local_csv, timeframe_to_timedelta
from backtest_engine import OptimizedBacktestRunner
from failure_analysis import FailureAnalyzer
import config

DATA_DIR = "data"
BACKTEST_START = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=30)
BACKTEST_END = pd.Timestamp.now(tz='UTC')

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "SOL/USDT:USDT",
]

TIMEFRAMES = ["5m", "1h", "4h"]


class CsvDataProvider:
    """خواندن داده‌ها از CSV برای تحلیل."""
    def __init__(self, symbols, data_dir):
        self.data = {}
        self.volumes = {}
        for sym in symbols:
            self.data[sym] = {}
            for tf in TIMEFRAMES:
                path = os.path.join(data_dir, f"{sym.replace('/', '_')}_{tf}.csv")
                if os.path.exists(path):
                    df = pd.read_csv(path, index_col=0, parse_dates=True)
                    df.index = pd.to_datetime(df.index, utc=True)
                    self.data[sym][tf] = df
                else:
                    self.data[sym][tf] = pd.DataFrame(columns=['open','high','low','close','volume'])
            # حجم فعلی به‌عنوان proxy
            self.volumes[sym] = 5_000_000.0

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe, pd.DataFrame())
        if start is not None:
            df = df[df.index >= start]
        if end is not None:
            df = df[df.index <= end]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volumes.get(symbol)


def main():
    print("=" * 70)
    print("SL FAILURE ANALYSIS RUNNER")
    print("=" * 70)

    provider = CsvDataProvider(SYMBOLS, DATA_DIR)
    runner = OptimizedBacktestRunner(
        provider,
        SYMBOLS,
        initial_balance=1000.0,
        fee_rate=0.0005,
        slippage_rate=0.0002,
    )

    print("اجرای بک‌تست...")
    result = runner.run(start_date=BACKTEST_START, end_date=BACKTEST_END)
    trades = result.get("trades", [])
    print(f"تعداد کل معاملات: {len(trades)}")

    analyzer = FailureAnalyzer(provider, SYMBOLS)
    sl_rows, summary = analyzer.analyze(trades)

    analyzer.print_report(summary)

    sl_csv, summary_csv = analyzer.write_csvs(sl_rows, summary, output_dir="analysis")
    print(f"\nCSV خروجی:")
    print(f"  {sl_csv}")
    print(f"  {summary_csv}")


if __name__ == "__main__":
    main()
