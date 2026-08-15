# FILE: src/strategy/data/data_validator.py

"""
اعتبارسنجی داده OHLCV
"""

from typing import List, Dict, Any, Optional
from .data_types import (
    OHLCVCandle, DataValidationResult, DataValidationError
)


class OHLCVDataValidator:
    """
    اعتبارسنجی کامل داده OHLCV تاریخی
    """
    
    REQUIRED_FIELDS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    def __init__(self):
        pass
    
    def validate_candles(
        self,
        candles: List[Dict[str, Any]],
        expected_interval_seconds: Optional[int] = None,
        timezone: str = "UTC"
    ) -> DataValidationResult:
        """
        اعتبارسنجی کامل لیست کندل‌ها
        
        Args:
            candles: لیست کندل‌ها
            expected_interval_seconds: فاصله زمانی مورد انتظار (اختیاری)
            timezone: timezone داده
        
        Returns:
            DataValidationResult
        """
        result = DataValidationResult()
        
        if not candles:
            result.is_valid = False
            result.errors.append("Empty dataset")
            return result
        
        # بررسی فیلدهای ضروری
        for i, candle in enumerate(candles):
            for field in self.REQUIRED_FIELDS:
                if field not in candle:
                    result.is_valid = False
                    result.errors.append(f"Candle {i}: missing field '{field}'")
        
        if not result.is_valid:
            return result
        
        # بررسی هر کندل
        for i, candle in enumerate(candles):
            try:
                ohlcv = OHLCVCandle(
                    timestamp=int(candle['timestamp']),
                    open=float(candle['open']),
                    high=float(candle['high']),
                    low=float(candle['low']),
                    close=float(candle['close']),
                    volume=float(candle['volume']),
                )
                errors = ohlcv.validate()
                
                if errors:
                    result.is_valid = False
                    for e in errors:
                        result.errors.append(f"Candle {i}: {e}")
            except (ValueError, TypeError) as e:
                result.is_valid = False
                result.errors.append(f"Candle {i}: conversion error: {e}")
        
        if not result.is_valid:
            return result
        
        # بررسی timestamps
        timestamps = [int(c['timestamp']) for c in candles]
        
        # بررسی منفی
        for i, ts in enumerate(timestamps):
            if ts < 0:
                result.is_valid = False
                result.errors.append(f"Candle {i}: negative timestamp: {ts}")
        
        if not result.is_valid:
            return result
        
        # بررسی مرتب‌سازی صعودی
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                result.is_valid = False
                result.errors.append(
                    f"Unsorted timestamps: index {i} ({timestamps[i]}) < index {i-1} ({timestamps[i-1]})"
                )
                break
        
        if not result.is_valid:
            return result
        
        # بررسی تکراری
        seen = set()
        for i, ts in enumerate(timestamps):
            if ts in seen:
                result.duplicate_count += 1
                result.errors.append(f"Duplicate timestamp at index {i}: {ts}")
            seen.add(ts)
        
        if result.duplicate_count > 0:
            result.is_valid = False
        
        # بررسی gap
        if expected_interval_seconds is not None and expected_interval_seconds > 0:
            for i in range(1, len(timestamps)):
                diff = timestamps[i] - timestamps[i-1]
                
                if diff > expected_interval_seconds:
                    result.gap_count += 1
                    result.gap_details.append({
                        'index': i,
                        'prev_timestamp': timestamps[i-1],
                        'current_timestamp': timestamps[i],
                        'gap_seconds': diff,
                        'expected_interval': expected_interval_seconds,
                    })
                    result.warnings.append(
                        f"Gap at index {i}: {diff} seconds (expected {expected_interval_seconds})"
                    )
        
        return result
    
    def validate_csv_rows(self, rows: List[Dict[str, str]]) -> DataValidationResult:
        """اعتبارسنجی ردیف‌های CSV"""
        candles = []
        
        for row in rows:
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
                result = DataValidationResult(is_valid=False)
                result.errors.append(f"CSV row conversion error: {e}")
                return result
        
        return self.validate_candles(candles)
