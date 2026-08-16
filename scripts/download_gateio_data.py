# FILE: scripts/download_gateio_data.py

"""
اسکریپت دانلود داده تاریخی از Gate.io USDT-M Perpetual Futures

نحوه استفاده:
python scripts/download_gateio_data.py --symbol BTC_USDT --timeframe 1h
python scripts/download_gateio_data.py --all  # دانلود هر ۱۲ نماد
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.gate_io_downloader import GateIODownloader, GateIODownloadError
from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.data.data_types import DatasetInfo
from src.strategy.config.trading_universe import TradingUniverseConfig


def main():
    parser = argparse.ArgumentParser(
        description='Download Gate.io USDT-M Perpetual Futures historical OHLCV data'
    )
    parser.add_argument('--symbol', default='BTC_USDT', help='Symbol (default: BTC_USDT)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (default: 1h)')
    parser.add_argument('--start', type=int, default=None, help='Start timestamp (unix seconds)')
    parser.add_argument('--end', type=int, default=None, help='End timestamp (unix seconds)')
    parser.add_argument('--output', default='data/historical', help='Output directory')
    parser.add_argument('--all', action='store_true', help='Download all 12 symbols')
    
    args = parser.parse_args()
    
    universe = TradingUniverseConfig()
    downloader = GateIODownloader()
    loader = HistoricalDataLoader()
    
    symbols = universe.symbols if args.all else [args.symbol]
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"Downloading {symbol} {args.timeframe} from Gate.io Futures...")
        
        try:
            candles = downloader.fetch_ohlcv(
                symbol=symbol,
                timeframe=args.timeframe,
                start_timestamp=args.start,
                end_timestamp=args.end
            )
        except GateIODownloadError as e:
            print(f"DOWNLOAD FAILED for {symbol}: {e}")
            continue
        
        print(f"Downloaded {len(candles)} candles")
        
        if not candles:
            print(f"No data for {symbol}")
            continue
        
        validation = loader.validator.validate_candles(candles)
        
        if not validation.is_valid:
            print(f"DATA VALIDATION FAILED for {symbol}:")
            for err in validation.errors[:5]:
                print(f"  - {err}")
            continue
        
        if validation.gap_count > 0:
            print(f"WARNING: {validation.gap_count} gaps")
        
        os.makedirs(args.output, exist_ok=True)
        
        csv_path = os.path.join(args.output, f"{symbol}_{args.timeframe}.csv")
        meta_path = os.path.join(args.output, f"{symbol}_{args.timeframe}.json")
        
        loader.save_csv(candles, csv_path)
        
        info = DatasetInfo(
            symbol=symbol,
            timeframe=args.timeframe,
            source="Gate.io USDT-M Perpetual Futures",
            start_timestamp=candles[0]['timestamp'],
            end_timestamp=candles[-1]['timestamp'],
            row_count=len(candles),
            timezone="UTC",
            checksum=loader._calculate_checksum(csv_path),
            download_timestamp=int(datetime.now(timezone.utc).timestamp()),
        )
        
        loader.save_metadata(info, meta_path)
        
        print(f"Saved: {csv_path}")
        print(f"Rows: {info.row_count}")
        print(f"Checksum: {info.checksum[:16]}...")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
