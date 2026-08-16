# FILE: scripts/run_backtest.py

"""
اسکریپت اجرای Backtest روی داده تاریخی واقعی

نحوه استفاده:
python scripts/run_backtest.py --symbol BTC_USDT --timeframe 1h
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.backtest.backtest_runner import BacktestRunner, BacktestRunnerConfig
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
    """ساخت پیکربندی کامل Pipeline با FTR Engine"""
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
    parser = argparse.ArgumentParser(description='Run FTR Backtest on Gate.io historical data')
    parser.add_argument('--symbol', default='BTC_USDT', help='Symbol')
    parser.add_argument('--timeframe', default='1h', help='Timeframe')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--initial-equity', type=float, default=1000.0, help='Initial equity')
    
    args = parser.parse_args()
    
    loader = HistoricalDataLoader()
    
    csv_path = os.path.join(args.data_dir, f"{args.symbol}_{args.timeframe}.csv")
    
    if not os.path.exists(csv_path):
        print(f"ERROR: Dataset not found: {csv_path}")
        print(f"Run download first:")
        print(f"  python scripts/download_gateio_data.py --symbol {args.symbol} --timeframe {args.timeframe}")
        return 1
    
    print(f"[1/4] Loading data...")
    
    candles, dataset_info, validation = loader.load_csv(
        csv_path,
        symbol=args.symbol,
        timeframe=args.timeframe,
        source="Gate.io USDT-M Perpetual Futures"
    )
    
    if not validation.is_valid:
        print("DATA VALIDATION FAILED:")
        for err in validation.errors[:10]:
            print(f"  - {err}")
        return 1
    
    print(f"  Rows: {dataset_info.row_count}")
    print(f"  Start: {datetime.fromtimestamp(dataset_info.start_timestamp, tz=timezone.utc)}")
    print(f"  End: {datetime.fromtimestamp(dataset_info.end_timestamp, tz=timezone.utc)}")
    
    print(f"[2/4] Building Pipeline...")
    
    # ساخت Pipeline با FTR Engine
    pipeline_config = build_pipeline_config(args.symbol, args.timeframe, args.initial_equity)
    pipeline = StrategyPipeline(pipeline_config)
    
    print(f"[3/4] Running Backtest...")
    
    # اجرای کامل Pipeline
    total_ftr_zones = 0
    total_ftb_events = 0
    total_qualified = 0
    total_watch = 0
    total_rejected = 0
    total_trade_signals = 0
    total_risk_accepted = 0
    total_orders = 0
    
    equity = args.initial_equity
    
    for current_index in range(2, len(candles)):
        visible_ohlcv = candles[:current_index + 1]
        
        result = pipeline.process_candle(visible_ohlcv, current_index)
        
        total_ftr_zones += len(pipeline.ftr_engine.get_all_zones())
        
        for signal in result.signals:
            if signal.status == "COMPLETE":
                total_qualified += 1
                total_trade_signals += 1
                if signal.risk_assessment and signal.risk_assessment.is_valid:
                    total_risk_accepted += 1
                    if signal.execution_result and signal.execution_result.success:
                        total_orders += 1
            elif signal.status == "WATCH":
                total_watch += 1
            elif signal.status in ["REJECTED", "RISK_REJECTED", "EXECUTION_REJECTED"]:
                total_rejected += 1
    
    print(f"[4/4] Generating Report...")
    
    print()
    print("=" * 50)
    print(f"FTR BACKTEST RESULT — {args.symbol}")
    print("=" * 50)
    print(f"Symbol:       {args.symbol}")
    print(f"Timeframe:    {args.timeframe}")
    print(f"Initial Eq:   ${args.initial_equity}")
    print(f"Final Eq:     ${equity:.2f}")
    print("-" * 50)
    print(f"FTR Zones:    {total_ftr_zones}")
    print(f"FTB Events:   {total_ftb_events}")
    print(f"QUALIFIED:    {total_qualified}")
    print(f"WATCH:        {total_watch}")
    print(f"REJECTED:     {total_rejected}")
    print(f"Trade Signals:{total_trade_signals}")
    print(f"Risk Accepted:{total_risk_accepted}")
    print(f"Orders:       {total_orders}")
    print("=" * 50)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
