# FILE: src/strategy/ftr/base_detector.py

"""
تشخیص ناحیه Base/Consolidation پس از Impulse
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.ftr_types import BaseData, DisplacementData


@dataclass
class BaseDetectorConfig:
    """پیکربندی تشخیص Base"""
    min_base_candles: int = 3  # حداقل تعداد کندل Base
    max_base_candles: int = 20  # حداکثر تعداد کندل Base
    max_retracement_pct: float = 0.382  # حداکثر بازگشت نسبت به Impulse
    max_base_range_pct: float = 0.30  # حداکثر محدوده Base نسبت به Impulse
    min_compression_ratio: float = 0.3  # حداقل نسبت فشردگی
    base_detection_method: str = "range_based"  # روش تشخیص Base
    
    def validate(self) -> List[str]:
        errors = []
        if self.min_base_candles < 1:
            errors.append("min_base_candles must be >= 1")
        if self.max_base_candles < self.min_base_candles:
            errors.append("max_base_candles must be >= min_base_candles")
        if self.max_retracement_pct <= 0:
            errors.append("max_retracement_pct must be > 0")
        if self.max_base_range_pct <= 0:
            errors.append("max_base_range_pct must be > 0")
        return errors


class BaseDetector:
    """
    تشخیص ناحیه Base (تثبیت قیمت پس از Impulse)
    
    Base = محدوده تثبیت قیمت که پس از حرکت Impulse شکل می‌گیرد
    و نشان‌دهنده عدم بازگشت سریع قیمت به سطح شکسته‌شده است.
    """
    
    def __init__(self, config: Optional[BaseDetectorConfig] = None):
        self.config = config or BaseDetectorConfig()
    
    def reset(self):
        """بازنشانی وضعیت"""
        pass
    
    def detect_base(self, ohlcv_data: List[dict], displacement: DisplacementData) -> Optional[BaseData]:
        """
        تشخیص Base پس از Impulse
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            displacement: داده جابجایی (Impulse)
        
        Returns:
            داده Base در صورت تشخیص معتبر
        """
        if displacement is None or not displacement.is_valid:
            return None
        
        start_index = displacement.end_index
        if start_index >= len(ohlcv_data) - 1:
            return None
        
        # جستجوی کندل‌های Base
        base_candles = []
        base_high = float('-inf')
        base_low = float('inf')
        
        for i in range(start_index, min(start_index + self.config.max_base_candles, len(ohlcv_data))):
            candle = ohlcv_data[i]
            
            # به‌روزرسانی محدوده Base
            base_high = max(base_high, candle['high'])
            base_low = min(base_low, candle['low'])
            
            # بررسی بازگشت بیش از حد
            if displacement.direction == "LONG":
                retracement = (displacement.end_price - candle['low']) / displacement.distance
            else:
                retracement = (candle['high'] - displacement.end_price) / displacement.distance
            
            if retracement > self.config.max_retracement_pct:
                break
            
            base_candles.append(i)
            
            # بررسی پایان Base
            if len(base_candles) >= self.config.min_base_candles:
                if self._is_base_complete(ohlcv_data, base_candles, displacement):
                    break
        
        # اعتبارسنجی Base
        if len(base_candles) < self.config.min_base_candles:
            return None
        
        # محاسبه محدوده Base
        base_high = max(ohlcv_data[i]['high'] for i in base_candles)
        base_low = min(ohlcv_data[i]['low'] for i in base_candles)
        base_range = base_high - base_low
        
        # بررسی حداکثر محدوده Base
        if displacement.distance > 0:
            base_range_ratio = base_range / displacement.distance
            if base_range_ratio > self.config.max_base_range_pct:
                return None
        
        # محاسبه کیفیت Base
        quality_score = self._calculate_base_quality(ohlcv_data, base_candles, base_high, base_low)
        compression_ratio = self._calculate_compression_ratio(ohlcv_data, base_candles)
        
        base_data = BaseData(
            high=base_high,
            low=base_low,
            start_timestamp=ohlcv_data[base_candles[0]]['timestamp'],
            end_timestamp=ohlcv_data[base_candles[-1]]['timestamp'],
            start_index=base_candles[0],
            end_index=base_candles[-1],
            quality_score=quality_score,
            compression_ratio=compression_ratio
        )
        
        return base_data
    
    def _is_base_complete(self, ohlcv_data: List[dict], base_candles: List[int],
                         displacement: DisplacementData) -> bool:
        """بررسی تکمیل Base"""
        if not base_candles:
            return False
        
        last_candle = ohlcv_data[base_candles[-1]]
        
        # بررسی خروج از Base
        if displacement.direction == "LONG":
            # خروج صعودی از Base
            if last_candle['close'] > last_candle['open']:
                body = last_candle['close'] - last_candle['open']
                range_val = last_candle['high'] - last_candle['low']
                
                if range_val > 0 and body / range_val > 0.5:
                    return True
        else:
            # خروج نزولی از Base
            if last_candle['close'] < last_candle['open']:
                body = last_candle['open'] - last_candle['close']
                range_val = last_candle['high'] - last_candle['low']
                
                if range_val > 0 and body / range_val > 0.5:
                    return True
        
        return False
    
    def _calculate_base_quality(self, ohlcv_data: List[dict], base_candles: List[int],
                               base_high: float, base_low: float) -> float:
        """محاسبه کیفیت Base"""
        if not base_candles:
            return 0.0
        
        # کیفیت بر اساس فشردگی و ثبات
        total_quality = 0.0
        
        for idx in base_candles:
            candle = ohlcv_data[idx]
            range_val = candle['high'] - candle['low']
            
            if range_val > 0 and base_high > base_low:
                # نسبت Range کندل به Range کل Base
                range_ratio = range_val / (base_high - base_low)
                
                # کیفیت بالاتر برای Range کوچک‌تر (فشردگی بیشتر)
                quality = 1.0 - min(range_ratio, 1.0)
                total_quality += quality
        
        avg_quality = total_quality / len(base_candles) if base_candles else 0.0
        
        return min(avg_quality, 1.0)
    
    def _calculate_compression_ratio(self, ohlcv_data: List[dict], base_candles: List[int]) -> float:
        """محاسبه نسبت فشردگی"""
        if not base_candles:
            return 0.0
        
        # مقایسه Range اول و آخر Base
        first_range = ohlcv_data[base_candles[0]]['high'] - ohlcv_data[base_candles[0]]['low']
        last_range = ohlcv_data[base_candles[-1]]['high'] - ohlcv_data[base_candles[-1]]['low']
        
        if first_range == 0:
            return 0.0
        
        # فشردگی = کاهش Range در طول Base
        compression = 1.0 - (last_range / first_range)
        
        return max(compression, 0.0)
