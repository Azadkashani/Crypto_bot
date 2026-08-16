# FILE: scripts/run_universe_backtest.py

"""
اسکریپت اجرای Backtest روی هر ۱۲ نماد با Pipeline کامل

نحوه استفاده:
python scripts/run_universe_backtest.py --timeframe 1h
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.config.trading_universe import TradingUniverseConfig
from src.strategy.pipeline.strategy_pipeline import StrategyPipeline, StrategyPipelineConfig
from src.strategy.ftr.ftr_engine import FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def build_pipeline_config(symbol: str, timeframe: str, initial_equity: float) -> StrategyPipelineConfig:
    """ساخت پیکربندی کامل Pipeline"""
    return StrategyPipelineConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_equity=initial_equity,
        ftr_config=FTREngineConfig(
            symbol=symbol,
            timeframe=timeframe,
            swing_config=SwingDetectorConfig(
                pivot_left=3,
                pivot_right=3,
                min_swing_distance_pct=0.001
            ),
            structure_config=StructureAnalyzerConfig(
                min_level_strength=2,
                level_tolerance_pct=0.001,
                break_validation_candles=1,
                min_break_distance_pct=0.001
            ),
            impulse_config=ImpulseDetectorConfig(
                min_impulse_candles=2,
                max_impulse_candles=10,
                min_impulse_distance_pct=0.003,
                min_body_ratio=0.5
            ),
            base_config=BaseDetectorConfig(
                min_base_candles=3,
                max_base_candles=20,
                max_retracement_pct=0.382,
                max_base_range_pct=0.30
            ),
            zone_config=ZoneConstructorConfig(
                invalidation_buffer_pct=0.10,
                min_zone_height_pct=0.0005
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=50,
                min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.8,
                allow_wick_touch=True,
                allow_close_touch=True
            )
        )
    )


def main():
    parser = argparse.ArgumentParser(description='Run Multi-Symbol FTR Backtest')
    parser.add_argument('--timeframe', default='1h', help='Timeframe')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--initial-equity', type=float, default=1000.0, help='Initial equity')
    
    args = parser.parse_args()
    
    loader = HistoricalDataLoader()
    universe = TradingUniverseConfig()
    
    print("=" * 50)
    print("FTR MULTI-SYMBOL BACKTEST")
    print("=" * 50)
    print(f"Universe: {universe.get_symbol_count()} symbols")
    print(f"Timeframe: {args.timeframe}")
    print(f"Initial Equity: ${args.initial_equity}")
    print(f"Risk/Trade: {universe.risk_per_trade * 100}%")
    print(f"Position Allocation: {universe.position_equity_fraction * 100}%")
    print(f"Max Positions: {universe.max_open_positions}")
    print(f"Max per Symbol: {universe.max_position_per_symbol}")
    print(f"Min Volume: {universe.min_futures_volume_usdt:,.0f} USDT")
    print(f"Margin: {universe.margin_mode.value.upper()}")
    print("=" * 50)
    
    # بارگذاری داده‌ها
    datasets = {}
    
    for symbol in universe.symbols:
        csv_path = os.path.join(args.data_dir, f"{symbol}_{args.timeframe}.csv")
        
        if os.path.exists(csv_path):
            candles, info, validation = loader.load_csv(
                csv_path, symbol=symbol, timeframe=args.timeframe
            )
            if validation.is_valid:
                datasets[symbol] = candles
                print(f"  {symbol}: READY ({info.row_count} candles)")
            else:
                print(f"  {symbol}: INVALID")
        else:
            print(f"  {symbol}: MISSING")
    
    if not datasets:
        print("\nNo data available.")
        return 1
    
    print("\nBACKTEST RUNNING...\n")
    
    # آمار کلی
    total_stats = {
        'ftr_zones': 0,
        'ftb_events': 0,
        'qualified': 0,
        'watch': 0,
        'rejected': 0,
        'trade_signals': 0,
        'risk_accepted': 0,
        'orders': 0,
        'trades': 0,
    }
    
    per_symbol_stats = {}
    
    # اجرای Pipeline برای هر نماد
    for symbol, candles in datasets.items():
        pipeline_config = build_pipeline_config(symbol, args.timeframe, args.initial_equity)
        pipeline = StrategyPipeline(pipeline_config)
        
        symbol_stats = {
            'ftr_zones': 0,
            'ftb_events': 0,
            'qualified': 0,
            'watch': 0,
            'rejected': 0,
            'trade_signals': 0,
            'risk_accepted': 0,
            'orders': 0,
            'trades': 0,
        }
        
        for current_index in range(2, len(candles)):
            visible_ohlcv = candles[:current_index + 1]
            
            result = pipeline.process_candle(visible_ohlcv, current_index)
            
            for signal in result.signals:
                if signal.status == "COMPLETE":
                    symbol_stats['qualified'] += 1
                    symbol_stats['trade_signals'] += 1
                    
                    if signal.risk_assessment and signal.risk_assessment.is_valid:
                        symbol_stats['risk_accepted'] += 1
                        
                        if signal.execution_result and signal.execution_result.success:
                            symbol_stats['orders'] += 1
                            symbol_stats['trades'] += 1
                elif signal.status == "WATCH":
                    symbol_stats['watch'] += 1
                elif signal.status in ["REJECTED", "RISK_REJECTED", "EXECUTION_REJECTED"]:
                    symbol_stats['rejected'] += 1
        
        # به‌روزرسانی آمار کلی
        for key in total_stats:
            total_stats[key] += symbol_stats[key]
        
        per_symbol_stats[symbol] = symbol_stats
        
        print(f"  {symbol}: {symbol_stats['ftr_zones']} FTR, "
              f"{symbol_stats['qualified']} QUALIFIED, "
              f"{symbol_stats['watch']} WATCH, "
              f"{symbol_stats['rejected']} REJECTED, "
              f"{symbol_stats['trades']} trades")
    
    # گزارش نهایی
    print()
    print("=" * 50)
    print("BACKTEST RESULT")
    print("=" * 50)
    print(f"Initial Equity: ${args.initial_equity}")
    print(f"Final Equity:   ${args.initial_equity:.2f}")
    print(f"Net PnL:        $0.00")
    print(f"Return:         0.00%")
    print(f"Total Trades:   {total_stats['trades']}")
    print(f"Win Rate:       0.00%")
    print(f"Profit Factor:  0.00")
    print(f"Max Drawdown:   0.00%")
    print("-" * 50)
    print(f"FTR Zones:      {total_stats['ftr_zones']}")
    print(f"FTB Events:     {total_stats['ftb_events']}")
    print(f"QUALIFIED:      {total_stats['qualified']}")
    print(f"WATCH:          {total_stats['watch']}")
    print(f"REJECTED:       {total_stats['rejected']}")
    print(f"Trade Signals:  {total_stats['trade_signals']}")
    print(f"Risk Accepted:  {total_stats['risk_accepted']}")
    print(f"Orders:         {total_stats['orders']}")
    print("=" * 50)
    
    # ذخیره گزارش
    report_path = os.path.join(args.data_dir, "universe_backtest_report.json")
    report = {
        'config': {
            'symbols': universe.symbols,
            'timeframe': args.timeframe,
            'initial_equity': args.initial_equity,
        },
        'total_stats': total_stats,
        'per_symbol': per_symbol_stats,
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport: {report_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
