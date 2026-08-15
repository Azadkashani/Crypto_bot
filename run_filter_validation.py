#!/usr/bin/env python3
"""
اجرای V4 — اعتبارسنجی فیلترهای Candidate به روش Chronological.

این اسکریپت:
    - بک‌تست را با تنظیمات فعلی اجرا می‌کند.
    - ویژگی‌های هر معامله را با FailureAnalyzer V2 استخراج می‌کند.
    - تقسیم chronological Train/Validation/OOS انجام می‌دهد.
    - همه فیلترهای کاندید را اعتبارسنجی می‌کند.
    - Sensitivity و Robustness و Overfitting را ارزیابی می‌کند.
    - خروجی CSV و JSON تولید می‌کند.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import timezone, timedelta

from historical_data import load_local_csv, timeframe_to_timedelta
from backtest_engine import OptimizedBacktestRunner
from failure_analysis import FailureAnalyzer
from analysis.filter_validation import (
    CANDIDATE_FILTERS,
    COMBINATION_FILTERS,
    validate_filter,
    calculate_robustness_score,
    determine_verdict,
    detect_overfitting,
    sensitivity_sl_atr,
    sensitivity_rsi,
    summarize_rows,
    chronological_split,
)

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
    print("SL FAILURE ANALYSIS V4 — FILTER VALIDATION")
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

    # بررسی Baseline
    baseline = summarize_rows(enriched_rows)
    print("\nBASELINE:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")

    train, val, oos = chronological_split(enriched_rows, train_ratio=0.6, val_ratio=0.2)
    print(f"\nTRAIN: {len(train)} trades")
    print(f"VALIDATION: {len(val)} trades")
    print(f"OUT-OF-SAMPLE: {len(oos)} trades")
    print(f"Total split: {len(train)+len(val)+len(oos)} trades")

    os.makedirs("analysis", exist_ok=True)

    # اعتبارسنجی فیلترهای تکی
    validation_results = []
    for name, cond in CANDIDATE_FILTERS.items():
        metrics = validate_filter(enriched_rows, name, cond)
        metrics["robustness_score"] = calculate_robustness_score(metrics)
        metrics["verdict"] = determine_verdict(metrics, metrics["robustness_score"])
        metrics["overfitting_check"] = detect_overfitting(metrics)
        validation_results.append(metrics)

    filter_df = pd.DataFrame(validation_results)
    filter_df.to_csv("analysis/v4_filter_validation.csv", index=False)

    # اعتبارسنجی ترکیب‌ها
    combo_results = []
    for name, cond in COMBINATION_FILTERS.items():
        metrics = validate_filter(enriched_rows, name, cond)
        metrics["robustness_score"] = calculate_robustness_score(metrics)
        metrics["verdict"] = determine_verdict(metrics, metrics["robustness_score"])
        metrics["overfitting_check"] = detect_overfitting(metrics)
        combo_results.append(metrics)

    combo_df = pd.DataFrame(combo_results)
    combo_df.to_csv("analysis/v4_filter_combinations.csv", index=False)

    # Sensitivity SL/ATR
    sl_atr_thresholds = [2.0, 2.5, 3.0, 3.5, 4.0]
    sens_sl = sensitivity_sl_atr(enriched_rows, sl_atr_thresholds)
    sens_sl.to_csv("analysis/v4_sensitivity_sl_atr.csv", index=False)

    # Sensitivity RSI LONG
    rsi_long_thresholds = [40, 45, 50]
    sens_rsi_long = sensitivity_rsi(enriched_rows, rsi_long_thresholds, "LONG")
    sens_rsi_long.to_csv("analysis/v4_sensitivity_rsi.csv", index=False)

    # Robustness summary
    robustness_df = filter_df[["filter", "oos_trades", "oos_expectancy", "oos_pf", "robustness_score", "verdict", "overfitting_check"]]
    robustness_df.to_csv("analysis/v4_robustness.csv", index=False)

    # Overfitting report
    overfit_df = filter_df[["filter", "train_exp_change", "val_exp_change", "oos_exp_change", "overfitting_check"]]
    overfit_df.to_csv("analysis/v4_overfitting_report.csv", index=False)

    # JSON report
    report = {
        "baseline": baseline,
        "split_sizes": {"train": len(train), "validation": len(val), "oos": len(oos)},
        "individual_filters": validation_results,
        "combinations": combo_results,
    }
    with open("analysis/v4_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    # چاپ خلاصه
    print("\n" + "=" * 70)
    print("FILTER ROBUSTNESS")
    print("=" * 70)
    print(f"{'Filter':<45}{'OOS Tr':>7}{'OOS Exp':>10}{'OOS PF':>10}{'Score':>7}{'Verdict':>12}")
    for r in validation_results:
        print(f"{r['filter']:<45}{r['oos_trades']:>7}{r['oos_expectancy']:>10.4f}{r['oos_pf']:>10.2f}{r['robustness_score']:>7.1f}{r['verdict']:>12}")

    print("\nBEST COMBINATIONS")
    print("=" * 70)
    print(f"{'Combination':<55}{'OOS Tr':>7}{'OOS Exp':>10}{'OOS PF':>10}{'Score':>7}{'Verdict':>12}")
    for r in combo_results:
        print(f"{r['filter']:<55}{r['oos_trades']:>7}{r['oos_expectancy']:>10.4f}{r['oos_pf']:>10.2f}{r['robustness_score']:>7.1f}{r['verdict']:>12}")

    print("\nOVERFITTING CHECK")
    print("=" * 70)
    for r in validation_results:
        if r["overfitting_check"] != "OK":
            print(f"{r['filter']}: {r['overfitting_check']}")

    print("\nFINAL RECOMMENDATION")
    print("=" * 70)
    strong = [r for r in validation_results if r["verdict"] == "STRONG"]
    moderate = [r for r in validation_results if r["verdict"] == "MODERATE"]
    reject = [r for r in validation_results if r["verdict"] == "REJECT"]
    print(f"STRONG CANDIDATES: {[r['filter'] for r in strong]}")
    print(f"MODERATE CANDIDATES: {[r['filter'] for r in moderate]}")
    print(f"REJECT: {[r['filter'] for r in reject]}")
    print("Do NOT automatically modify the live strategy.")


if __name__ == "__main__":
    main()
