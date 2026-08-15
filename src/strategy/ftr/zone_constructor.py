# FILE: src/strategy/ftr/zone_constructor.py

"""
ساخت FTR Zone از اجزای شناسایی شده
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import StructureLevel, StructureBreak
from ..types.ftr_types import (
    FTRZone, FTRZoneState, DisplacementData, BaseData, FTRDirection
)


@dataclass
class ZoneConstructorConfig:
    """پیکربندی ساخت Zone"""
    invalidation_buffer_pct: float = 0.10  # بافر ابطال (10% ارتفاع Base)
    min_zone_height_pct: float = 0.0005  # حداقل ارتفاع Zone (0.05%)
    use_base_boundaries: bool = True  # استفاده از مرزهای Base برای Zone
    
    def validate(self) -> List[str]:
        errors = []
        if self.invalidation_buffer_pct < 0:
            errors.append("invalidation_buffer_pct must be >= 0")
        if self.min_zone_height_pct <= 0:
            errors.append("min_zone_height_pct must be > 0")
        return errors


class ZoneConstructor:
    """
    ساخت FTR Zone از داده‌های شناسایی شده
    
    Zone = محدوده‌ای که از مرزهای Base استخراج می‌شود
    و نشان‌دهنده ناحیه‌ای است که قیمت باید به آن بازگردد.
    """
    
    def __init__(self, config: Optional[ZoneConstructorConfig] = None):
        self.config = config or ZoneConstructorConfig()
        self._zone_counter = 0
    
    def reset(self):
        """بازنشانی شمارنده Zone"""
        self._zone_counter = 0
    
    def construct_zone(self, symbol: str, timeframe: str, direction: str,
                      structure_level: StructureLevel, structure_break: StructureBreak,
                      displacement: DisplacementData, base: BaseData,
                      current_timestamp: int) -> Optional[FTRZone]:
        """
        ساخت FTR Zone
        
        Args:
            symbol: نماد معاملاتی
            timeframe: تایم‌فریم
            direction: جهت ("LONG" یا "SHORT")
            structure_level: سطح ساختاری شکسته شده
            structure_break: اطلاعات شکست
            displacement: داده جابجایی
            base: داده Base
            current_timestamp: timestamp فعلی
        
        Returns:
            FTR Zone ساخته شده
        """
        if not all([structure_level, displacement, base]):
            return None
        
        if not displacement.is_valid or not base.is_valid:
            return None
        
        # تعیین مرزهای Zone از Base
        if self.config.use_base_boundaries:
            zone_high = base.high
            zone_low = base.low
        else:
            # استفاده از نقاط میانی
            midpoint = base.midpoint
            half_height = base.height / 2
            zone_high = midpoint + half_height
            zone_low = midpoint - half_height
        
        # بررسی حداقل ارتفاع Zone
        if zone_high > 0:
            zone_height_pct = (zone_high - zone_low) / zone_high
            if zone_height_pct < self.config.min_zone_height_pct:
                return None
        
        # محاسبه نقطه ابطال
        if direction == "LONG":
            invalidation_level = base.low - (base.height * self.config.invalidation_buffer_pct)
        else:
            invalidation_level = base.high + (base.height * self.config.invalidation_buffer_pct)
        
        # ایجاد شناسه Zone
        self._zone_counter += 1
        zone_id = f"FTR_{direction}_{self._zone_counter}_{current_timestamp}"
        
        # ساخت Zone
        zone = FTRZone(
            zone_id=zone_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            zone_high=zone_high,
            zone_low=zone_low,
            zone_midpoint=(zone_high + zone_low) / 2,
            created_timestamp=current_timestamp,
            structure_reference=structure_level,
            structure_break=structure_break,
            displacement=displacement,
            base=base,
            invalidation_level=invalidation_level,
            state=FTRZoneState.CREATED,
            diagnostic_info={
                'base_height': base.height,
                'base_duration': base.duration_bars,
                'displacement_distance': displacement.distance,
                'displacement_candles': displacement.candle_count,
                'break_price': structure_break.break_price,
                'break_direction': structure_break.direction
            }
        )
        
        return zone
    
    def validate_zone(self, zone: FTRZone) -> bool:
        """اعتبارسنجی Zone ساخته شده"""
        if zone is None:
            return False
        
        # بررسی مرزهای Zone
        if zone.zone_high <= zone.zone_low:
            return False
        
        if zone.zone_high <= 0 or zone.zone_low <= 0:
            return False
        
        # بررسی نقطه ابطال
        if zone.direction == "LONG":
            if zone.invalidation_level >= zone.zone_low:
                return False
        else:
            if zone.invalidation_level <= zone.zone_high:
                return False
        
        # بررسی داده‌های مورد نیاز
        if zone.displacement is None or zone.base is None:
            return False
        
        if zone.structure_reference is None:
            return False
        
        return True
