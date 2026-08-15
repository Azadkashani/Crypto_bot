# FILE: src/strategy/ftr/ftb_detector.py

"""
تشخیص First Time Back به FTR Zone
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.ftr_types import (
    FTRZone, FTRZoneState, FTBEvent, FTBTouchType
)


@dataclass
class FTBDetectorConfig:
    """پیکربندی تشخیص FTB"""
    max_ftb_wait_candles: int = 50  # حداکثر کندل انتظار برای FTB
    min_touch_depth_pct: float = 0.0  # حداقل عمق نفوذ (0% = فقط لمس مرز)
    max_touch_depth_pct: float = 1.0  # حداکثر عمق نفوذ (100% = کل Zone)
    allow_wick_touch: bool = True  # اجازه لمس با سایه
    allow_close_touch: bool = True  # اجازه لمس با بسته‌شدن
    require_reversal_confirmation: bool = False  # نیاز به تأیید بازگشت
    
    def validate(self) -> List[str]:
        errors = []
        if self.max_ftb_wait_candles < 1:
            errors.append("max_ftb_wait_candles must be >= 1")
        if self.min_touch_depth_pct < 0:
            errors.append("min_touch_depth_pct must be >= 0")
        if self.max_touch_depth_pct > 1:
            errors.append("max_touch_depth_pct must be <= 1")
        return errors


class FTBDetector:
    """
    تشخیص First Time Back به FTR Zone
    
    این کلاس بررسی می‌کند که آیا قیمت برای اولین بار به Zone بازگشته است
    و آیا این بازگشت معتبر است یا خیر.
    """
    
    def __init__(self, config: Optional[FTBDetectorConfig] = None):
        self.config = config or FTBDetectorConfig()
        self._tracked_zones: Dict[str, FTRZone] = {}
    
    def reset(self):
        """بازنشانی وضعیت"""
        self._tracked_zones.clear()
    
    def add_zone(self, zone: FTRZone):
        """افزودن Zone برای ردیابی"""
        self._tracked_zones[zone.zone_id] = zone
    
    def remove_zone(self, zone_id: str):
        """حذف Zone از ردیابی"""
        if zone_id in self._tracked_zones:
            del self._tracked_zones[zone_id]
    
    def check_ftb(self, ohlcv_data: List[dict], current_index: int,
                 zone: FTRZone) -> Optional[FTBEvent]:
        """
        بررسی First Time Back برای Zone
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            current_index: ایندکس کندل جاری
            zone: FTR Zone مورد بررسی
        
        Returns:
            رویداد FTB در صورت تشخیص
        """
        # بررسی وضعیت Zone
        if zone.state != FTRZoneState.ACTIVE:
            return None
        
        # بررسی زمان انتظار
        if current_index - zone.base.end_index > self.config.max_ftb_wait_candles:
            zone.update_state(FTRZoneState.EXPIRED)
            return None
        
        current_candle = ohlcv_data[current_index]
        current_high = current_candle['high']
        current_low = current_candle['low']
        current_close = current_candle['close']
        
        # بررسی ورود قیمت به Zone
        touch_detected = False
        touch_price = 0.0
        touch_type = None
        
        if zone.direction == "LONG":
            # برای LONG: قیمت از بالا به Zone برمی‌گردد
            if self.config.allow_wick_touch and current_low <= zone.zone_high:
                touch_detected = True
                touch_price = current_low
                touch_type = FTBTouchType.WICK
            
            if self.config.allow_close_touch and current_close <= zone.zone_high:
                touch_detected = True
                touch_price = current_close
                touch_type = FTBTouchType.CLOSE
                
                # بررسی نفوذ عمیق
                if current_close <= zone.zone_low:
                    touch_type = FTBTouchType.PENETRATION
        else:
            # برای SHORT: قیمت از پایین به Zone برمی‌گردد
            if self.config.allow_wick_touch and current_high >= zone.zone_low:
                touch_detected = True
                touch_price = current_high
                touch_type = FTBTouchType.WICK
            
            if self.config.allow_close_touch and current_close >= zone.zone_low:
                touch_detected = True
                touch_price = current_close
                touch_type = FTBTouchType.CLOSE
                
                if current_close >= zone.zone_high:
                    touch_type = FTBTouchType.PENETRATION
        
        if not touch_detected or touch_type is None:
            return None
        
        # بررسی عمق نفوذ
        if not self._validate_touch_depth(zone, touch_price):
            return None
        
        # ایجاد رویداد FTB
        ftb_event = FTBEvent(
            zone=zone,
            timestamp=current_candle['timestamp'],
            price=touch_price,
            touch_type=touch_type
        )
        
        # اعتبارسنجی FTB
        ftb_event.is_valid = self._validate_ftb(ohlcv_data, current_index, ftb_event)
        
        if ftb_event.is_valid:
            # ثبت لمس در Zone
            zone.register_touch(touch_price, current_candle['timestamp'], touch_type)
            ftb_event.validation_reasons.append("Valid first touch to FTR zone")
        else:
            ftb_event.validation_reasons.append("FTB validation failed")
        
        return ftb_event
    
    def _validate_touch_depth(self, zone: FTRZone, touch_price: float) -> bool:
        """اعتبارسنجی عمق نفوذ"""
        zone_height = zone.zone_height
        
        if zone_height == 0:
            return False
        
        if zone.direction == "LONG":
            # محاسبه عمق نفوذ از بالای Zone
            penetration = zone.zone_high - touch_price
        else:
            # محاسبه عمق نفوذ از پایین Zone
            penetration = touch_price - zone.zone_low
        
        penetration_pct = penetration / zone_height
        
        return self.config.min_touch_depth_pct <= penetration_pct <= self.config.max_touch_depth_pct
    
    def _validate_ftb(self, ohlcv_data: List[dict], current_index: int,
                     ftb_event: FTBEvent) -> bool:
        """اعتبارسنجی رویداد FTB"""
        if ftb_event.zone is None:
            return False
        
        # بررسی اینکه این اولین لمس است
        if ftb_event.zone.touch_count > 0:
            return False
        
        # بررسی عدم ابطال Zone
        if ftb_event.zone.state == FTRZoneState.INVALIDATED:
            return False
        
        # تأیید بازگشت (اختیاری)
        if self.config.require_reversal_confirmation:
            if current_index >= len(ohlcv_data) - 1:
                return False
            
            next_candle = ohlcv_data[current_index + 1]
            
            if ftb_event.zone.direction == "LONG":
                # کندل بعدی باید صعودی باشد
                if next_candle['close'] <= next_candle['open']:
                    return False
            else:
                # کندل بعدی باید نزولی باشد
                if next_candle['close'] >= next_candle['open']:
                    return False
        
        return True
