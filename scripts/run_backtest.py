# FILE: scripts/run_backtest.py

"""
اسکریپت اجرای Backtest روی داده تاریخی واقعی

نحوه استفاده:
python scripts/run_backtest.py --symbol BTC_USDT --timeframe 1h

پیش‌نیاز:
ابتدا داده را دانلود کنید:
python scripts/download_gateio_data.py --symbol BTC_USDT --timeframe 1h
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.backtest.backtest_runner import BacktestRunner, BacktestRunnerConfig
from src.strategy.validation.strategy_validator import StrategyValidator
from src.strategy.config.trading_universe import TradingUniverseConfig
from src.strategy.pipeline.strategy_pipeline import StrategyPipelineConfig
from src.strategy.ftr.ftr_engine import FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def build_pipeline_config(symbol: str, timeframe: str) -> StrategyPipelineConfig:
    """ساخت پیکربندی Pipeline"""
    return StrategyPipelineConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_equity=10000.0,
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
    parser = argparse.ArgumentParser(description='Run FTR Backtest on historical Gate.io data')
    parser.add_argument('--symbol', default='BTC_USDT', help='Symbol (default: BTC_USDT)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (default: 1h)')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--initial-equity', type=float, default=10000.0, help='Initial equity')
    
    args = parser.parse_args()
    
    loader = HistoricalDataLoader()
    
    csv_path = os.path.join(args.data_dir, f"{args.symbol}_{args.timeframe}.csv")
    meta_path = os.path.join(args.data_dir, f"{args.symbol}_{args.timeframe}.json")
    
    # بررسی وجود فایل
    if not os.path.exists(csv_path):
        print(f"ERROR: Dataset not found: {csv_path}")
        print(f"Run download first:")
        print(f"  python scripts/download_gateio_data.py --symbol {args.symbol} --timeframe {args.timeframe}")
        return 1
    
    print(f"[1/4] Loading data: {csv_path}")
    
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
    print(f"  Gaps: {validation.gap_count}")
    print(f"  Duplicates: {validation.duplicate_count}")
    
    print(f"[2/4] Running Backtest...")
    
    # بررسی Universe
    universe = TradingUniverseConfig()
    if not universe.is_symbol_allowed(args.symbol):
        print(f"ERROR: Symbol {args.symbol} is not in the 12-symbol universe")
        return 1
    
    # ساخت Validator
    validator = StrategyValidator()
    
    # اجرای Validation (که Backtest را هم اجرا می‌کند)
    report = validator.validate(
        ohlcv_data=candles,
        symbol=args.symbol,
        timeframe=args.timeframe,
        filename=os.path.basename(csv_path)
    )
    
    print(f"[3/4] Generating Report...")
    
    # چاپ گزارش
    text_report = report.generate_text_report()
    print()
    print(text_report)
    
    # ذخیره گزارش
    report_path = os.path.join(args.data_dir, f"{args.symbol}_{args.timeframe}_report.json")
    with open(report_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    
    print(f"[4/4] Report saved: {report_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
