# FILE: src/strategy/ftr/breakout_detector.py

"""
تشخیص شکست ساختاری معتبر برای FTR
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import StructureLevel, StructureBreak, BreakType
from ..types.ftr_types import DisplacementData


@dataclass
class BreakoutDetectorConfig:
    """پیکربندی تشخیص شکست"""
    break_method: str = "close"  # "close" یا "wick"
    min_break_distance_pct: float = 0.001  # حداقل فاصله شکست (0.1%)
    min_break_strength: float = 0.5  # حداقل قدرت شکست
    use_volume_confirmation: bool = False  # استفاده از حجم (اختیاری)
    min_volume_ratio: float = 1.5  # حداقل نسبت حجم
    confirmation_candles: int = 1  # تعداد کندل تأیید
    
    def validate(self) -> List[str]:
        errors = []
        if self.break_method not in ["close", "wick"]:
            errors.append("break_method must be 'close' or 'wick'")
        if self.min_break_distance_pct <= 0:
            errors.append("min_break_distance_pct must be > 0")
        if self.confirmation_candles < 1:
            errors.append("confirmation_candles must be >= 1")
        return errors


class BreakoutDetector:
    """
    تشخیص و اعتبارسنجی شکست ساختاری
    
    این کلاس تشخیص می‌دهد که آیا قیمت از یک سطح مهم ساختاری عبور کرده است
    و آیا این شکست معتبر است یا خیر.
    """
    
    def __init__(self, config: Optional[BreakoutDetectorConfig] = None):
        self.config = config or BreakoutDetectorConfig()
        self._pending_breaks: List[Dict[str, Any]] = []
        self._confirmed_breaks: List[Dict[str, Any]] = []
    
    def reset(self):
        """بازنشانی وضعیت"""
        self._pending_breaks.clear()
        self._confirmed_breaks.clear()
    
    def detect_breakout(self, ohlcv_data: List[dict], current_index: int,
                       structure_level: StructureLevel) -> Optional[Dict[str, Any]]:
        """
        تشخیص شکست سطح ساختاری
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            current_index: ایندکس کندل جاری
            structure_level: سطح ساختاری برای بررسی
        
        Returns:
            اطلاعات شکست در صورت تشخیص، None در غیر این صورت
        """
        if current_index < 1:
            return None
        
        current_candle = ohlcv_data[current_index]
        current_close = current_candle['close']
        current_high = current_candle['high']
        current_low = current_candle['low']
        
        # بررسی شکست مقاومت (LONG)
        if structure_level.level_type in ["RESISTANCE", "SUPPLY"]:
            if self._is_resistance_broken(current_candle, structure_level.price):
                break_info = self._create_break_info(
                    ohlcv_data, current_index, structure_level, "LONG"
                )
                
                # اعتبارسنجی شکست
                if self._validate_break(ohlcv_data, current_index, break_info):
                    self._confirmed_breaks.append(break_info)
                    return break_info
        
        # بررسی شکست حمایت (SHORT)
        elif structure_level.level_type in ["SUPPORT", "DEMAND"]:
            if self._is_support_broken(current_candle, structure_level.price):
                break_info = self._create_break_info(
                    ohlcv_data, current_index, structure_level, "SHORT"
                )
                
                if self._validate_break(ohlcv_data, current_index, break_info):
                    self._confirmed_breaks.append(break_info)
                    return break_info
        
        return None
    
    def get_confirmed_breaks(self) -> List[Dict[str, Any]]:
        """دریافت شکست‌های تأیید شده"""
        return self._confirmed_breaks.copy()
    
    def _is_resistance_broken(self, candle: dict, level_price: float) -> bool:
        """بررسی شکست مقاومت"""
        if self.config.break_method == "close":
            return candle['close'] > level_price
        elif self.config.break_method == "wick":
            return candle['high'] > level_price
        return False
    
    def _is_support_broken(self, candle: dict, level_price: float) -> bool:
        """بررسی شکست حمایت"""
        if self.config.break_method == "close":
            return candle['close'] < level_price
        elif self.config.break_method == "wick":
            return candle['low'] < level_price
        return False
    
    def _create_break_info(self, ohlcv_data: List[dict], break_index: int,
                          level: StructureLevel, direction: str) -> Dict[str, Any]:
        """ایجاد اطلاعات شکست"""
        break_candle = ohlcv_data[break_index]
        break_price = break_candle['close'] if direction == "LONG" else break_candle['close']
        
        # محاسبه فاصله شکست
        if direction == "LONG":
            break_distance = (break_price - level.price) / level.price
        else:
            break_distance = (level.price - break_price) / level.price
        
        # محاسبه قدرت شکست
        break_strength = self._calculate_break_strength(ohlcv_data, break_index, direction)
        
        return {
            'break_index': break_index,
            'break_price': break_price,
            'break_distance': break_distance,
            'break_strength': break_strength,
            'direction': direction,
            'level': level,
            'timestamp': break_candle['timestamp']
        }
    
    def _validate_break(self, ohlcv_data: List[dict], break_index: int,
                       break_info: Dict[str, Any]) -> bool:
        """اعتبارسنجی شکست"""
        # بررسی حداقل فاصله شکست
        if break_info['break_distance'] < self.config.min_break_distance_pct:
            return False
        
        # بررسی حداقل قدرت شکست
        if break_info['break_strength'] < self.config.min_break_strength:
            return False
        
        # بررسی تأیید با کندل‌های بعدی
        if self.config.confirmation_candles > 0:
            if break_index + self.config.confirmation_candles >= len(ohlcv_data):
                return False
            
            direction = break_info['direction']
            level_price = break_info['level'].price
            
            for i in range(break_index + 1, break_index + 1 + self.config.confirmation_candles):
                close = ohlcv_data[i]['close']
                
                if direction == "LONG" and close <= level_price:
                    return False
                elif direction == "SHORT" and close >= level_price:
                    return False
        
        # بررسی حجم (اختیاری)
        if self.config.use_volume_confirmation and 'volume' in ohlcv_data[break_index]:
            # محاسبه میانگین حجم
            volumes = [c.get('volume', 0) for c in ohlcv_data[max(0, break_index-20):break_index]]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            
            if avg_volume > 0:
                volume_ratio = ohlcv_data[break_index]['volume'] / avg_volume
                if volume_ratio < self.config.min_volume_ratio:
                    return False
        
        return True
    
    def _calculate_break_strength(self, ohlcv_data: List[dict], break_index: int,
                                 direction: str) -> float:
        """محاسبه قدرت شکست"""
        candle = ohlcv_data[break_index]
        body = abs(candle['close'] - candle['open'])
        range_val = candle['high'] - candle['low']
        
        if range_val == 0:
            return 0.0
        
        # نسبت بدنه به Range
        body_ratio = body / range_val
        
        # موقعیت بسته‌شدن در کندل
        if direction == "LONG":
            close_position = (candle['close'] - candle['low']) / range_val
        else:
            close_position = (candle['high'] - candle['close']) / range_val
        
        # ترکیب معیارها
        strength = (body_ratio * 0.6) + (close_position * 0.4)
        
        return min(strength, 1.0)
