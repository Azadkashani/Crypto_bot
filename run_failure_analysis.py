#!/usr/bin/env python3
"""
اجرای تحلیل SL Failure Analysis V2.

این اسکریپت:
    - داده‌های CSV محلی را می‌خواند.
    - بک‌تست بهینه‌شده را اجرا می‌کند.
    - تحلیل جامع SL/TP را انجام می‌دهد.
    - خروجی‌های CSV و JSON تولید می‌کند.
"""

import os
import pandas as pd
from datetime import timezone, timedelta

from historical_data import load_local_csv, timeframe_to_timedelta
from backtest_engine import OptimizedBacktestRunner
from failure_analysis import FailureAnalyzer
import config


DATA_DIR = "data"

NOW = pd.Timestamp.now(tz='UTC')
BACKTEST_END = NOW.floor('4h') - pd.Timedelta(hours=4)
BACKTEST_START = BACKTEST_END - pd.Timedelta(days=30)

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "SOL/USDT:USDT",
]

TIMEFRAMES = ["5m", "1h", "4h"]


class DictHistoricalDataProvider:
    """Provider ساده بر پایه دیتافریم‌های ذخیره‌شده در حافظه."""
    def __init__(self, data, volumes):
        self.data = data
        self.volumes = volumes

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe)
        if df is None:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volumes.get(symbol)


def load_data_for_symbols(symbols, timeframes, data_dir):
    data_store = {}
    volume_cache = {}
    for sym in symbols:
        data_store[sym] = {}
        for tf in timeframes:
            df = load_local_csv(sym, tf, data_dir)
            if df is not None:
                warmup_delta = timedelta(seconds=500 * timeframe_to_timedelta(tf).total_seconds())
                data_start = BACKTEST_START - warmup_delta
                mask = (df.index >= data_start) & (df.index <= BACKTEST_END)
                df = df.loc[mask]
                data_store[sym][tf] = df
            else:
                data_store[sym][tf] = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        volume_cache[sym] = 5_000_000.0  # proxy

    return DictHistoricalDataProvider(data_store, volume_cache)


def main():
    print("=" * 70)
    print("SL FAILURE ANALYSIS V2 RUNNER")
    print("=" * 70)

    provider = load_data_for_symbols(SYMBOLS, TIMEFRAMES, DATA_DIR)

    print("اجرای بک‌تست...")
    runner = OptimizedBacktestRunner(
        provider,
        SYMBOLS,
        initial_balance=1000.0,
        fee_rate=0.0005,
        slippage_rate=0.0002,
    )

    result = runner.run(start_date=BACKTEST_START, end_date=BACKTEST_END)
    trades = result.get("trades", [])
    print(f"تعداد کل معاملات: {len(trades)}")

    analyzer = FailureAnalyzer(provider, SYMBOLS)
    report = analyzer.analyze(trades)

    analyzer.print_report(report)

    files = analyzer.write_outputs(report, output_dir="analysis")
    print("\nفایل‌های خروجی:")
    for key, path in files.items():
        print(f"  {key}: {path}")


if __name__ == "__main__":
    main()
