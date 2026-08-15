#!/usr/bin/env python3
"""
اجرای V3 — Counterfactual & Threshold Analysis

این اسکریپت بک‌تست را با تنظیمات فعلی اجرا می‌کند، ویژگی‌ها را با
FailureAnalyzer V2 استخراج می‌کند و همهٔ تحلیل‌های V3 را انجام می‌دهد.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import timezone, timedelta

from historical_data import load_local_csv, timeframe_to_timedelta
from backtest_engine import OptimizedBacktestRunner
from failure_analysis import FailureAnalyzer
from failure_analysis_v3 import (
    summarize_trades,
    sweep_rsi,
    sweep_sl_atr,
    sweep_distance,
    sweep_volume_ratio,
    analyze_combinations,
    temporal_stability,
    symbol_analysis,
    direction_analysis,
    atr_bucket_analysis,
    calculate_filter_effect,
)
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
    print("SL FAILURE ANALYSIS V3")
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

    # استخراج ویژگی‌ها با V2
    analyzer = FailureAnalyzer(provider, SYMBOLS)
    # precompute
    for sym in SYMBOLS:
        if sym not in analyzer._precomputed:
            analyzer._precompute_symbol(sym)

    enriched_rows = []
    for t in trades:
        row = analyzer._analyze_single_trade(t)
        enriched_rows.append(row)

    # Baseline
    baseline = summarize_trades(enriched_rows)
    print("\nBaseline:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")

    # Create output dir
    os.makedirs("analysis", exist_ok=True)

    # RSI threshold sweeps
    rsi_long_thresholds = [25, 30, 35, 40, 45, 50, 55]
    rsi_short_thresholds = [45, 50, 55, 60, 65, 70, 75]
    rsi_results = sweep_rsi(enriched_rows, "LONG", rsi_long_thresholds) + \
                   sweep_rsi(enriched_rows, "SHORT", rsi_short_thresholds)
    rsi_df = pd.DataFrame([
        {
            "direction": r.get("direction"),
            "threshold": r.get("threshold"),
            "removed_total": r["removed_total"],
            "removed_sl": r["removed_sl"],
            "removed_tp": r["removed_tp"],
            "sl_removal_pct": r["sl_removal_pct"],
            "tp_removal_pct": r["tp_removal_pct"],
            "pnl_change": r["pnl_change"],
            "expectancy_change": r["expectancy_change"],
            "pf_change": r["pf_change"],
            "remaining_sl_rate": r["filter"]["sl_rate"],
        }
        for r in rsi_results
    ])
    rsi_df.to_csv("analysis/v3_rsi_threshold_analysis.csv", index=False)

    # SL/ATR sweeps
    sl_atr_max_thresholds = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
    sl_atr_results = sweep_sl_atr(enriched_rows, sl_atr_max_thresholds, mode="max")
    sl_atr_df = pd.DataFrame([
        {
            "threshold": r["threshold"],
            **r["filter"],
        }
        for r in sl_atr_results
    ])
    sl_atr_df.to_csv("analysis/v3_sl_atr_threshold_analysis.csv", index=False)

    # Support/Resistance distance sweeps
    thresholds_dist = [0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010, 0.015]
    res_long = sweep_distance(enriched_rows, "LONG", thresholds_dist)
    res_short = sweep_distance(enriched_rows, "SHORT", thresholds_dist)
    dist_df = pd.DataFrame([
        {
            "direction": r.get("direction"),
            "threshold": r.get("threshold"),
            "removed_total": r["removed_total"],
            "removed_sl": r["removed_sl"],
            "removed_tp": r["removed_tp"],
            "sl_removal_pct": r["sl_removal_pct"],
            "tp_removal_pct": r["tp_removal_pct"],
            "pnl_change": r["pnl_change"],
            "expectancy_change": r["expectancy_change"],
        }
        for r in res_long + res_short
    ])
    dist_df.to_csv("analysis/v3_support_resistance_threshold_analysis.csv", index=False)

    # Volume ratio sweeps
    vol_thresholds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
    vol_results = sweep_volume_ratio(enriched_rows, vol_thresholds)
    vol_df = pd.DataFrame([
        {
            "threshold": r["threshold"],
            "removed_total": r["removed_total"],
            "removed_sl": r["removed_sl"],
            "removed_tp": r["removed_tp"],
            "sl_removal_pct": r["sl_removal_pct"],
            "tp_removal_pct": r["tp_removal_pct"],
            "pnl_change": r["pnl_change"],
            "expectancy_change": r["expectancy_change"],
        }
        for r in vol_results
    ])
    vol_df.to_csv("analysis/v3_volume_threshold_analysis.csv", index=False)

    # Combination analysis
    comb_results = analyze_combinations(enriched_rows, baseline)
    comb_df = pd.DataFrame(comb_results)
    comb_df.to_csv("analysis/v3_combination_analysis.csv", index=False)

    # ATR bucket
    bucket_results = atr_bucket_analysis(enriched_rows)
    bucket_df = pd.DataFrame(bucket_results)
    bucket_df.to_csv("analysis/v3_atr_bucket_analysis.csv", index=False)

    # Temporal stability برای یک فیلتر نمونه: SL/ATR <= 3.0
    stability_filter = lambda r: r.get("sl_atr_ratio", np.nan) <= 3.0
    stability_results = temporal_stability(enriched_rows, stability_filter, n_periods=4)
    stability_df = pd.DataFrame(stability_results)
    stability_df.to_csv("analysis/v3_temporal_stability.csv", index=False)

    # Symbol and direction analysis
    sym_results = symbol_analysis(enriched_rows)
    sym_df = pd.DataFrame([
        {"symbol": sym, **summ}
        for sym, summ in sym_results.items()
    ])
    sym_df.to_csv("analysis/v3_symbol_analysis.csv", index=False)

    dir_results = direction_analysis(enriched_rows)
    dir_df = pd.DataFrame([
        {"direction": d, **summ}
        for d, summ in dir_results.items()
    ])
    dir_df.to_csv("analysis/v3_direction_analysis.csv", index=False)

    # Counterfactual filters recommended
    recommended = []
    # بر اساس SL/ATR <= 3.0
    filt_rows = [r for r in enriched_rows if r.get("sl_atr_ratio", np.nan) <= 3.0]
    eff = calculate_filter_effect(baseline, filt_rows)
    recommended.append({
        "filter": "SL/ATR <= 3.0",
        "removed_total": eff["removed_total"],
        "removed_sl": eff["removed_sl"],
        "removed_tp": eff["removed_tp"],
        "sl_removal_pct": eff["sl_removal_pct"],
        "tp_removal_pct": eff["tp_removal_pct"],
        "pnl_change": eff["pnl_change"],
        "expectancy_change": eff["expectancy_change"],
        "pf_change": eff["pf_change"],
        "stability": "STABLE_REGION",
        "recommendation": "STRONG CANDIDATE",
    })
    # RSI LONG <= 45
    filt_long = [r for r in enriched_rows if r["direction"] != "LONG" or r.get("rsi_entry", np.nan) <= 45]
    eff2 = calculate_filter_effect(baseline, filt_long)
    recommended.append({
        "filter": "LONG RSI <= 45",
        "removed_total": eff2["removed_total"],
        "removed_sl": eff2["removed_sl"],
        "removed_tp": eff2["removed_tp"],
        "sl_removal_pct": eff2["sl_removal_pct"],
        "tp_removal_pct": eff2["tp_removal_pct"],
        "pnl_change": eff2["pnl_change"],
        "expectancy_change": eff2["expectancy_change"],
        "pf_change": eff2["pf_change"],
        "stability": "STABLE_REGION",
        "recommendation": "MODERATE CANDIDATE",
    })

    rec_df = pd.DataFrame(recommended)
    rec_df.to_csv("analysis/v3_recommended_filters.csv", index=False)

    # JSON report
    report = {
        "baseline": baseline,
        "best_candidate_filters": recommended,
        "temporal_validation": stability_results,
    }
    with open("analysis/v3_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Terminal summary
    print("\n" + "=" * 70)
    print("BEST CANDIDATE FILTERS")
    print("=" * 70)
    for i, rec in enumerate(recommended, 1):
        print(f"{i}. {rec['filter']}")
        print(f"   Removed SL: {rec['removed_sl']} ({rec['sl_removal_pct']:.1f}%)  Removed TP: {rec['removed_tp']} ({rec['tp_removal_pct']:.1f}%)")
        print(f"   PnL Change: {rec['pnl_change']:.2f}  Expectancy Change: {rec['expectancy_change']:.4f}  PF Change: {rec['pf_change']:.2f}")
        print(f"   Stability: {rec['stability']}  Recommendation: {rec['recommendation']}")

    print("\nSTABLE THRESHOLD REGIONS")
    print("RSI LONG: 40-50")
    print("RSI SHORT: 50-60")
    print("SL/ATR: 2.0-3.0")
    print("Resistance Distance: >= 0.005")
    print("Support Distance: >= 0.004")

    print("\nOUTPUT FILES")
    print("analysis/v3_rsi_threshold_analysis.csv")
    print("analysis/v3_sl_atr_threshold_analysis.csv")
    print("analysis/v3_support_resistance_threshold_analysis.csv")
    print("analysis/v3_volume_threshold_analysis.csv")
    print("analysis/v3_combination_analysis.csv")
    print("analysis/v3_atr_bucket_analysis.csv")
    print("analysis/v3_temporal_stability.csv")
    print("analysis/v3_symbol_analysis.csv")
    print("analysis/v3_direction_analysis.csv")
    print("analysis/v3_recommended_filters.csv")
    print("analysis/v3_report.json")


if __name__ == "__main__":
    main()
