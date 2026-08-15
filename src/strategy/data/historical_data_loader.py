# FILE: src/strategy/data/historical_data_loader.py

"""
بارگذاری داده تاریخی OHLCV از CSV
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import csv
import os
import hashlib
import json
from .data_types import DatasetInfo, DataValidationResult
from .data_validator import OHLCVDataValidator


class HistoricalDataLoader:
    """
    بارگذاری و ذخیره‌سازی داده تاریخی OHLCV
    """
    
    REQUIRED_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    def __init__(self, validator: Optional[OHLCVDataValidator] = None):
        self.validator = validator or OHLCVDataValidator()
    
    def load_csv(
        self,
        file_path: str,
        symbol: str = "",
        timeframe: str = "",
        source: str = "CSV",
        timezone: str = "UTC"
    ) -> tuple[List[Dict[str, Any]], DatasetInfo, DataValidationResult]:
        """
        بارگذاری CSV و اعتبارسنجی آن
        
        Args:
            file_path: مسیر فایل CSV
            symbol: نماد
            timeframe: تایم‌فریم
            source: منبع داده
            timezone: timezone
        
        Returns:
            (candles, dataset_info, validation_result)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        candles = []
        
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            
            if reader.fieldnames is None:
                raise ValueError("CSV has no headers")
            
            for col in self.REQUIRED_COLUMNS:
                if col not in reader.fieldnames:
                    raise ValueError(f"Missing required column: {col}")
            
            for row in reader:
                try:
                    candle = {
                        'timestamp': int(row['timestamp']),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']),
                    }
                    candles.append(candle)
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Invalid CSV row: {e}")
        
        # تعیین interval از داده
        interval = self._detect_interval(candles)
        
        # اعتبارسنجی
        validation_result = self.validator.validate_candles(
            candles,
            expected_interval_seconds=interval,
            timezone=timezone
        )
        
        # Dataset Info
        dataset_info = DatasetInfo(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            start_timestamp=candles[0]['timestamp'] if candles else 0,
            end_timestamp=candles[-1]['timestamp'] if candles else 0,
            row_count=len(candles),
            timezone=timezone,
            checksum=self._calculate_checksum(file_path),
        )
        
        return candles, dataset_info, validation_result
    
    def save_csv(
        self,
        candles: List[Dict[str, Any]],
        file_path: str
    ) -> None:
        """
        ذخیره کندل‌ها به CSV
        
        Args:
            candles: لیست کندل‌ها
            file_path: مسیر خروجی
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.REQUIRED_COLUMNS)
            writer.writeheader()
            writer.writerows(candles)
    
    def save_metadata(
        self,
        dataset_info: DatasetInfo,
        file_path: str
    ) -> None:
        """
        ذخیره metadata به JSON
        
        Args:
            dataset_info: اطلاعات Dataset
            file_path: مسیر خروجی
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(dataset_info.to_dict(), f, indent=2)
    
    def load_metadata(self, file_path: str) -> DatasetInfo:
        """بارگذاری metadata از JSON"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Metadata file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return DatasetInfo(
            symbol=data.get('symbol', ''),
            timeframe=data.get('timeframe', ''),
            source=data.get('source', ''),
            start_timestamp=data.get('start_timestamp', 0),
            end_timestamp=data.get('end_timestamp', 0),
            row_count=data.get('row_count', 0),
            timezone=data.get('timezone', 'UTC'),
            checksum=data.get('checksum'),
            download_timestamp=data.get('download_timestamp'),
        )
    
    def _detect_interval(self, candles: List[Dict[str, Any]]) -> Optional[int]:
        """تشخیص فاصله زمانی از داده"""
        if len(candles) < 2:
            return None
        
        timestamps = [c['timestamp'] for c in candles]
        diffs = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        
        if not diffs:
            return None
        
        # پیدا کردن شایع‌ترین diff
        from collections import Counter
        most_common = Counter(diffs).most_common(1)[0][0]
        
        return most_common
    
    def _calculate_checksum(self, file_path: str) -> str:
        """محاسبه SHA256 فایل"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
