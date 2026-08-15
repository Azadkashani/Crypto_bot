# FILE: scripts/download_gateio_data.py

"""
اسکریپت دانلود داده تاریخی از Gate.io
"""

import sys
import os
import argparse
import json
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.gate_io_downloader import GateIODownloader
from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.data.data_types import DatasetInfo


def main():
    parser = argparse.ArgumentParser(description='Download Gate.io Futures historical OHLCV data')
    parser.add_argument('--symbol', default='BTC_USDT', help='Symbol (default: BTC_USDT)')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (default: 1h)')
    parser.add_argument('--start', type=int, default=None, help='Start timestamp (unix seconds)')
    parser.add_argument('--end', type=int, default=None, help='End timestamp (unix seconds)')
    parser.add_argument('--output', default='data/historical', help='Output directory')
    
    args = parser.parse_args()
    
    # ایجاد Downloader
    downloader = GateIODownloader()
    loader = HistoricalDataLoader()
    
    print(f"Downloading {args.symbol} {args.timeframe} from Gate.io...")
    
    # دانلود
    candles = downloader.fetch_ohlcv(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_timestamp=args.start,
        end_timestamp=args.end
    )
    
    print(f"Downloaded {len(candles)} candles")
    
    if not candles:
        print("No data downloaded")
        return 1
    
    # اعتبارسنجی
    validation = loader.validator.validate_candles(candles)
    
    if not validation.is_valid:
        print("DATA VALIDATION FAILED:")
        for err in validation.errors[:10]:
            print(f"  - {err}")
        return 1
    
    if validation.gap_count > 0:
        print(f"WARNING: {validation.gap_count} gaps detected")
    
    # ذخیره
    os.makedirs(args.output, exist_ok=True)
    
    csv_path = os.path.join(args.output, f"{args.symbol}_{args.timeframe}.csv")
    meta_path = os.path.join(args.output, f"{args.symbol}_{args.timeframe}.json")
    
    loader.save_csv(candles, csv_path)
    
    # Metadata
    info = DatasetInfo(
        symbol=args.symbol,
        timeframe=args.timeframe,
        source="Gate.io Futures",
        start_timestamp=candles[0]['timestamp'],
        end_timestamp=candles[-1]['timestamp'],
        row_count=len(candles),
        timezone="UTC",
        checksum=loader._calculate_checksum(csv_path),
        download_timestamp=int(datetime.now(timezone.utc).timestamp()),
    )
    
    loader.save_metadata(info, meta_path)
    
    print(f"Saved: {csv_path}")
    print(f"Metadata: {meta_path}")
    print(f"Checksum: {info.checksum}")
    print(f"Rows: {info.row_count}")
    print(f"Start: {datetime.fromtimestamp(info.start_timestamp, tz=timezone.utc)}")
    print(f"End: {datetime.fromtimestamp(info.end_timestamp, tz=timezone.utc)}")
    print(f"Gaps: {validation.gap_count}")
    print(f"Duplicates: {validation.duplicate_count}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
