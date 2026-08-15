# FILE: src/strategy/data/data_types.py

"""
تایپ‌های مخصوص Data Layer
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class DataValidationError(Exception):
    """خطای اعتبارسنجی داده"""
    pass


class TimeframeUnit(Enum):
    """واحد تایم‌فریم"""
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"
    WEEK = "w"


@dataclass
class OHLCVCandle:
    """یک کندل OHLCV"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
        }
    
    def validate(self) -> List[str]:
        """اعتبارسنجی کندل"""
        errors = []
        
        if self.timestamp < 0:
            errors.append("Negative timestamp")
        
        if self.open <= 0:
            errors.append(f"Invalid open: {self.open}")
        
        if self.high <= 0:
            errors.append(f"Invalid high: {self.high}")
        
        if self.low <= 0:
            errors.append(f"Invalid low: {self.low}")
        
        if self.close <= 0:
            errors.append(f"Invalid close: {self.close}")
        
        if self.volume < 0:
            errors.append(f"Invalid volume: {self.volume}")
        
        if self.high < self.low:
            errors.append(f"high ({self.high}) < low ({self.low})")
        
        if self.high < max(self.open, self.close):
            errors.append(f"high ({self.high}) < max(open, close)")
        
        if self.low > min(self.open, self.close):
            errors.append(f"low ({self.low}) > min(open, close)")
        
        return errors


@dataclass
class DatasetInfo:
    """اطلاعات Dataset"""
    symbol: str = ""
    timeframe: str = ""
    source: str = ""
    start_timestamp: int = 0
    end_timestamp: int = 0
    row_count: int = 0
    timezone: str = "UTC"
    checksum: Optional[str] = None
    download_timestamp: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'source': self.source,
            'start_timestamp': self.start_timestamp,
            'end_timestamp': self.end_timestamp,
            'row_count': self.row_count,
            'timezone': self.timezone,
            'checksum': self.checksum,
            'download_timestamp': self.download_timestamp,
        }


@dataclass
class DataValidationResult:
    """نتیجه اعتبارسنجی داده"""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duplicate_count: int = 0
    gap_count: int = 0
    gap_details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'duplicate_count': self.duplicate_count,
            'gap_count': self.gap_count,
            'gap_details': self.gap_details,
        }
