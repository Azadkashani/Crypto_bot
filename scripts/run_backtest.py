# FILE: scripts/run_backtest.py

"""
اسکریپت اجرای Backtest روی داده تاریخی واقعی

نحوه استفاده:
python scripts/run_backtest.py --symbol BTC_USDT --timeframe 1h
python scripts/run_backtest.py --all  # اجرا روی هر ۱۲ نماد
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.validation.strategy_validator import StrategyValidator
from src.strategy.config.trading_universe import TradingUniverseConfig


def main():
    parser = argparse.ArgumentParser(description='Run FTR Backtest on Gate.io historical data')
    parser.add_argument('--symbol', default='BTC_USDT', help='Symbol (default: BTC_USDT)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (default: 1h)')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--all', action='store_true', help='Run on all 12 symbols')
    
    args = parser.parse_args()
    
    universe = TradingUniverseConfig()
    loader = HistoricalDataLoader()
    
    symbols = universe.symbols if args.all else [args.symbol]
    
    all_results = {}
    
    for symbol in symbols:
        csv_path = os.path.join(args.data_dir, f"{symbol}_{args.timeframe}.csv")
        
        if not os.path.exists(csv_path):
            print(f"SKIP {symbol}: Dataset not found: {csv_path}")
            continue
        
        print(f"\n{'='*50}")
        print(f"BACKTEST: {symbol}")
        print(f"{'='*50}")
        
        candles, dataset_info, validation = loader.load_csv(
            csv_path,
            symbol=symbol,
            timeframe=args.timeframe,
            source="Gate.io USDT-M Perpetual Futures"
        )
        
        if not validation.is_valid:
            print(f"DATA VALIDATION FAILED for {symbol}")
            for err in validation.errors[:5]:
                print(f"  - {err}")
            continue
        
        print(f"Rows: {dataset_info.row_count}")
        print(f"Start: {datetime.fromtimestamp(dataset_info.start_timestamp, tz=timezone.utc)}")
        print(f"End: {datetime.fromtimestamp(dataset_info.end_timestamp, tz=timezone.utc)}")
        print(f"Gaps: {validation.gap_count}")
        
        validator = StrategyValidator()
        report = validator.validate(
            ohlcv_data=candles,
            symbol=symbol,
            timeframe=args.timeframe,
            filename=os.path.basename(csv_path)
        )
        
        text_report = report.generate_text_report()
        print(text_report)
        
        report_path = os.path.join(args.data_dir, f"{symbol}_{args.timeframe}_report.json")
        with open(report_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        print(f"Report: {report_path}")
        
        all_results[symbol] = report.to_dict()
    
    if args.all:
        summary_path = os.path.join(args.data_dir, "summary_report.json")
        with open(summary_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nSummary: {summary_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
