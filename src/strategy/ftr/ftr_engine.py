# FILE: src/strategy/ftr/ftr_engine.py

"""
موتور اصلی تشخیص FTR — هماهنگ‌کننده تمام اجزا
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from ..types.market_structure import (
    SwingPoint, SwingType, StructureLevel, StructureBreak,
    MarketStructureState, StructureType, BreakType
)
from ..types.ftr_types import (
    FTRZone, FTRZoneState, FTBEvent, DisplacementData, BaseData,
    FTRDetectionResult
)
from ..market_structure.swing_detector import SwingDetector, SwingDetectorConfig
from ..market_structure.structure_analyzer import StructureAnalyzer, StructureAnalyzerConfig
from .breakout_detector import BreakoutDetector, BreakoutDetectorConfig
from .impulse_detector import ImpulseDetector, ImpulseDetectorConfig
from .base_detector import BaseDetector, BaseDetectorConfig
from .zone_constructor import ZoneConstructor, ZoneConstructorConfig
from .ftb_detector import FTBDetector, FTBDetectorConfig


@dataclass
class FTREngineConfig:
    """پیکربندی موتور FTR"""
    symbol: str = ""
    timeframe: str = ""
    swing_config: Optional[SwingDetectorConfig] = None
    structure_config: Optional[StructureAnalyzerConfig] = None
    breakout_config: Optional[BreakoutDetectorConfig] = None
    impulse_config: Optional[ImpulseDetectorConfig] = None
    base_config: Optional[BaseDetectorConfig] = None
    zone_config: Optional[ZoneConstructorConfig] = None
    ftb_config: Optional[FTBDetectorConfig] = None
    
    def validate(self) -> List[str]:
        errors = []
        if not self.symbol:
            errors.append("symbol is required")
        if not self.timeframe:
            errors.append("timeframe is required")
        return errors


class FTREngine:
    """
    موتور اصلی تشخیص FTR
    
    این کلاس تمام اجزای تشخیص FTR را هماهنگ می‌کند:
    Structure → Displacement → Base → FTR Zone → FTB
    """
    
    def __init__(self, config: FTREngineConfig):
        self.config = config
        self.symbol = config.symbol
        self.timeframe = config.timeframe
        
        # راه‌اندازی اجزا
        self.structure_analyzer = StructureAnalyzer(config.structure_config)
        self.breakout_detector = BreakoutDetector(config.breakout_config)
        self.impulse_detector = ImpulseDetector(config.impulse_config)
        self.base_detector = BaseDetector(config.base_config)
        self.zone_constructor = ZoneConstructor(config.zone_config)
        self.ftb_detector = FTBDetector(config.ftb_config)
        
        # وضعیت داخلی
        self._active_zones: Dict[str, FTRZone] = {}
        self._all_zones: List[FTRZone] = []
        self._ftb_events: List[FTBEvent] = []
        self._pending_structures: List[Tuple[StructureLevel, StructureBreak]] = []
        
        # پیکربندی Swing
        if config.swing_config:
            self.structure_analyzer.swing_detector.config = config.swing_config
    
    def reset(self):
        """بازنشانی کامل موتور"""
        self.structure_analyzer.reset()
        self.breakout_detector.reset()
        self.impulse_detector.reset()
        self.base_detector.reset()
        self.zone_constructor.reset()
        self.ftb_detector.reset()
        self._active_zones.clear()
        self._all_zones.clear()
        self._ftb_events.clear()
        self._pending_structures.clear()
    
    def process_bar(self, ohlcv_data: List[dict], current_index: int) -> FTRDetectionResult:
        """
        پردازش کندل جاری و تشخیص FTR
        
        Args:
            ohlcv_data: لیست کامل کندل‌های OHLCV
            current_index: ایندکس کندل جاری
        
        Returns:
            نتیجه تشخیص FTR
        """
        result = FTRDetectionResult()
        
        if current_index < 2:
            return result
        
        # ۱. تحلیل ساختار بازار
        structure_state = self.structure_analyzer.process_bar(ohlcv_data, current_index)
        result.structure_state = structure_state
        
        # ۲. بررسی شکست‌های ساختاری
        structure_levels = self.structure_analyzer.get_structure_levels()
        
        for level in structure_levels:
            if level.is_consumed:
                continue
            
            breakout = self.breakout_detector.detect_breakout(
                ohlcv_data, current_index, level
            )
            
            if breakout:
                # ثبت ساختار شکسته شده
                structure_break = StructureBreak(
                    break_type=BreakType.BOS if structure_state.structure_type != StructureType.RANGING else BreakType.CHOCH,
                    break_price=breakout['break_price'],
                    break_timestamp=breakout['timestamp'],
                    broken_level=level,
                    direction=breakout['direction'],
                    is_valid=True,
                    validation_timestamp=current_index,
                    break_strength=breakout['break_strength']
                )
                
                self._pending_structures.append((level, structure_break))
                
                # ۳. تشخیص Impulse
                displacement = self.impulse_detector.detect_impulse(
                    ohlcv_data, breakout['break_index'], breakout['direction']
                )
                
                if displacement and displacement.is_valid:
                    # ۴. تشخیص Base
                    base = self.base_detector.detect_base(ohlcv_data, displacement)
                    
                    if base and base.is_valid:
                        # ۵. ساخت FTR Zone
                        zone = self.zone_constructor.construct_zone(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            direction=breakout['direction'],
                            structure_level=level,
                            structure_break=structure_break,
                            displacement=displacement,
                            base=base,
                            current_timestamp=ohlcv_data[current_index]['timestamp']
                        )
                        
                        if zone and self.zone_constructor.validate_zone(zone):
                            # ثبت Zone
                            zone.update_state(FTRZoneState.ACTIVE)
                            self._active_zones[zone.zone_id] = zone
                            self._all_zones.append(zone)
                            self.ftb_detector.add_zone(zone)
                            result.add_zone(zone)
                            result.add_diagnostic(f"FTR zone created: {zone.zone_id}")
        
        # ۶. بررسی FTB برای Zoneهای فعال
        for zone_id, zone in list(self._active_zones.items()):
            # بررسی ابطال Zone
            if self._check_invalidation(ohlcv_data, current_index, zone):
                zone.invalidate(ohlcv_data[current_index]['timestamp'])
                del self._active_zones[zone_id]
                result.add_diagnostic(f"Zone invalidated: {zone_id}")
                continue
            
            # بررسی FTB
            ftb_event = self.ftb_detector.check_ftb(ohlcv_data, current_index, zone)
            
            if ftb_event and ftb_event.is_valid:
                self._ftb_events.append(ftb_event)
                result.add_ftb(ftb_event)
                result.add_diagnostic(f"FTB detected: {zone_id}")
                
                # Zone استفاده شده
                zone.consume(ohlcv_data[current_index]['timestamp'])
                del self._active_zones[zone_id]
        
        return result
    
    def get_active_zones(self) -> List[FTRZone]:
        """دریافت Zoneهای فعال"""
        return list(self._active_zones.values())
    
    def get_all_zones(self) -> List[FTRZone]:
        """دریافت تمام Zoneها"""
        return self._all_zones.copy()
    
    def get_ftb_events(self) -> List[FTBEvent]:
        """دریافت رویدادهای FTB"""
        return self._ftb_events.copy()
    
    def _check_invalidation(self, ohlcv_data: List[dict], current_index: int,
                           zone: FTRZone) -> bool:
        """بررسی ابطال Zone"""
        current_candle = ohlcv_data[current_index]
        
        if zone.direction == "LONG":
            # ابطال LONG: قیمت به زیر نقطه ابطال بسته شود
            if current_candle['close'] < zone.invalidation_level:
                return True
        else:
            # ابطال SHORT: قیمت به بالای نقطه ابطال بسته شود
            if current_candle['close'] > zone.invalidation_level:
                return True
        
        return False
