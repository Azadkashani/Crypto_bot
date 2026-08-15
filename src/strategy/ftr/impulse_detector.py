# FILE: src/strategy/ftr/impulse_detector.py

"""
تشخیص حرکت Impulse پس از شکست ساختاری
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.ftr_types import DisplacementData


@dataclass
class ImpulseDetectorConfig:
    """پیکربندی تشخیص Impulse"""
    min_impulse_candles: int = 2  # حداقل تعداد کندل برای Impulse
    max_impulse_candles: int = 10  # حداکثر تعداد کندل برای Impulse
    min_impulse_distance_pct: float = 0.003  # حداقل فاصله حرکت (0.3%)
    min_body_ratio: float = 0.5  # حداقل نسبت بدنه کندل‌ها
    impulse_end_method: str = "reversal_candle"  # روش تشخیص پایان Impulse
    max_retracement_during_impulse: float = 0.25  # حداکثر بازگشت در طول Impulse
    
    def validate(self) -> List[str]:
        errors = []
        if self.min_impulse_candles < 1:
            errors.append("min_impulse_candles must be >= 1")
        if self.max_impulse_candles < self.min_impulse_candles:
            errors.append("max_impulse_candles must be >= min_impulse_candles")
        if self.min_impulse_distance_pct <= 0:
            errors.append("min_impulse_distance_pct must be > 0")
        return errors


class ImpulseDetector:
    """
    تشخیص حرکت Impulse (جابجایی قوی)
    
    Impulse = حرکت قدرتمند و جهت‌دار پس از شکست ساختار
    """
    
    def __init__(self, config: Optional[ImpulseDetectorConfig] = None):
        self.config = config or ImpulseDetectorConfig()
    
    def reset(self):
        """بازنشانی وضعیت"""
        pass
    
    def detect_impulse(self, ohlcv_data: List[dict], break_index: int,
                      direction: str) -> Optional[DisplacementData]:
        """
        تشخیص حرکت Impulse پس از شکست
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            break_index: ایندکس کندل شکست
            direction: جهت حرکت ("LONG" یا "SHORT")
        
        Returns:
            داده جابجایی در صورت تشخیص Impulse معتبر
        """
        if break_index >= len(ohlcv_data) - 1:
            return None
        
        start_index = break_index
        start_candle = ohlcv_data[break_index]
        start_price = start_candle['close']
        
        max_distance = 0.0
        end_index = start_index
        end_price = start_price
        current_extreme = start_price
        
        # ردیابی حرکت در جهت مشخص
        impulse_candles = []
        
        for i in range(break_index + 1, min(break_index + 1 + self.config.max_impulse_candles, len(ohlcv_data))):
            candle = ohlcv_data[i]
            
            if direction == "LONG":
                # حرکت صعودی
                if candle['close'] > current_extreme:
                    current_extreme = candle['close']
                    end_index = i
                    end_price = candle['close']
                    max_distance = end_price - start_price
                    impulse_candles.append(i)
                else:
                    # بررسی بازگشت
                    retracement = (current_extreme - candle['close']) / max_distance if max_distance > 0 else 1.0
                    
                    if retracement > self.config.max_retracement_during_impulse:
                        break
                    elif self._is_reversal_candle(candle, direction):
                        break
            
            elif direction == "SHORT":
                # حرکت نزولی
                if candle['close'] < current_extreme:
                    current_extreme = candle['close']
                    end_index = i
                    end_price = candle['close']
                    max_distance = start_price - end_price
                    impulse_candles.append(i)
                else:
                    retracement = (candle['close'] - current_extreme) / max_distance if max_distance > 0 else 1.0
                    
                    if retracement > self.config.max_retracement_during_impulse:
                        break
                    elif self._is_reversal_candle(candle, direction):
                        break
        
        # اعتبارسنجی Impulse
        if len(impulse_candles) < self.config.min_impulse_candles:
            return None
        
        if max_distance <= 0:
            return None
        
        # بررسی حداقل فاصله
        min_distance = start_price * self.config.min_impulse_distance_pct
        if max_distance < min_distance:
            return None
        
        # ایجاد داده جابجایی
        displacement = DisplacementData(
            start_price=start_price,
            end_price=end_price,
            start_timestamp=start_candle['timestamp'],
            end_timestamp=ohlcv_data[end_index]['timestamp'],
            direction=direction,
            candle_count=len(impulse_candles),
            strength_score=self._calculate_impulse_strength(ohlcv_data, impulse_candles, direction),
            avg_candle_range=self._calculate_avg_candle_range(ohlcv_data, impulse_candles),
            start_index=start_index,
            end_index=end_index
        )
        
        return displacement
    
    def _is_reversal_candle(self, candle: dict, direction: str) -> bool:
        """بررسی کندل بازگشتی"""
        body = abs(candle['close'] - candle['open'])
        range_val = candle['high'] - candle['low']
        
        if range_val == 0:
            return False
        
        body_ratio = body / range_val
        
        if direction == "LONG":
            # کندل نزولی با بدنه قابل توجه
            return candle['close'] < candle['open'] and body_ratio > self.config.min_body_ratio
        else:
            # کندل صعودی با بدنه قابل توجه
            return candle['close'] > candle['open'] and body_ratio > self.config.min_body_ratio
        
        return False
    
    def _calculate_impulse_strength(self, ohlcv_data: List[dict], 
                                   impulse_indices: List[int], direction: str) -> float:
        """محاسبه قدرت Impulse"""
        if not impulse_indices:
            return 0.0
        
        total_strength = 0.0
        
        for idx in impulse_indices:
            candle = ohlcv_data[idx]
            body = abs(candle['close'] - candle['open'])
            range_val = candle['high'] - candle['low']
            
            if range_val > 0:
                body_ratio = body / range_val
                
                # بررسی جهت صحیح
                if direction == "LONG" and candle['close'] > candle['open']:
                    total_strength += body_ratio
                elif direction == "SHORT" and candle['close'] < candle['open']:
                    total_strength += body_ratio
        
        avg_strength = total_strength / len(impulse_indices) if impulse_indices else 0.0
        
        return min(avg_strength, 1.0)
    
    def _calculate_avg_candle_range(self, ohlcv_data: List[dict],
                                   impulse_indices: List[int]) -> float:
        """محاسبه میانگین Range کندل‌های Impulse"""
        if not impulse_indices:
            return 0.0
        
        total_range = 0.0
        
        for idx in impulse_indices:
            candle = ohlcv_data[idx]
            total_range += candle['high'] - candle['low']
        
        return total_range / len(impulse_indices) if impulse_indices else 0.0
