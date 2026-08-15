#!/usr/bin/env python3
"""
اجرای Walk-Forward Validation مخصوص SL/ATR.

این اسکریپت:
    - بک‌تست را با تنظیمات فعلی اجرا می‌کند.
    - ویژگی‌های هر معامله را با FailureAnalyzer V2 استخراج می‌کند.
    - فقط تحلیل Walk-Forward روی SL/ATR انجام می‌دهد.
"""

import os
import pandas as pd
from datetime import timezone, timedelta

from historical_data import load_local_csv, timeframe_to_timedelta
from backtest_engine import OptimizedBacktestRunner
from failure_analysis import FailureAnalyzer
from sl_atr_walk_forward import run_walk_forward, CANDIDATE_THRESHOLDS

import config


DATA_DIR = "data"
BACKTEST_END = pd.Timestamp.now(tz='UTC').floor('4h') - pd.Timedelta(hours=4)
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
        volume_cache[sym] = 5_000_000.0

    return DictHistoricalDataProvider(data_store, volume_cache)


def main():
    print("=" * 70)
    print("SL/ATR WALK-FORWARD VALIDATION")
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

    # استخراج ویژگی‌ها
    analyzer = FailureAnalyzer(provider, SYMBOLS)
    for sym in SYMBOLS:
        if sym not in analyzer._precomputed:
            analyzer._precompute_symbol(sym)

    enriched_rows = []
    for t in trades:
        row = analyzer._analyze_single_trade(t)
        enriched_rows.append(row)

    # فقط معاملاتی که sl_atr_ratio دارند
    valid_rows = [r for r in enriched_rows if r.get("sl_atr_ratio") is not None]

    print(f"معاملات دارای SL/ATR: {len(valid_rows)}")

    # اجرای Walk-Forward
    report = run_walk_forward(
        valid_rows,
        thresholds=CANDIDATE_THRESHOLDS,
        initial_train_size=40,
        validation_size=20,
        output_dir="analysis",
    )

    # چاپ خلاصه
    print("\n" + "=" * 70)
    print("WALK-FORWARD SUMMARY")
    print("=" * 70)
    print(f"Number of windows: {report['summary']['number_of_windows']}")
    print(f"Baseline PnL: {report['summary']['baseline_total_pnl']:.2f}")
    print(f"Baseline Expectancy: {report['summary']['baseline_expectancy']:.4f} R")
    print(f"Baseline PF: {report['summary']['baseline_pf']:.2f}")
    print("-" * 70)
    print("Threshold Selection & Validation Performance:")
    for th in CANDIDATE_THRESHOLDS:
        stats = next((x for x in report["summary"]["thresholds"] if x["threshold"] == th), None)
        if not stats:
            continue
        print(f"\nSL/ATR <= {th}")
        print(f"  Selected: {stats['times_selected']} times")
        print(f"  Avg Validation Expectancy: {stats['average_validation_expectancy']:.4f} R")
        print(f"  Avg Validation PF: {stats['average_validation_pf']:.2f}")
        print(f"  Positive Windows: {stats['positive_validation_windows']}/{stats['validation_windows_tested']}")
        print(f"  Total Validation PnL: {stats['total_validation_pnl']:.2f}")

    print("\nخروجی‌ها:")
    print("analysis/sl_atr_walk_forward.csv")
    print("analysis/sl_atr_walk_forward_thresholds.csv")
    print("analysis/sl_atr_walk_forward_summary.json")
    print("analysis/sl_atr_walk_forward_report.txt")


if __name__ == "__main__":
    main()
