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
    
    Pipeline:
    Structure Break → Pending → Impulse → Base → FTR Zone → FTB
    
    اصل حیاتی:
    - فقط داده تا current_index قابل مشاهده است
    - Break فقط پس از ثبت واقعی پردازش می‌شود
    - Break ناقص Pending باقی می‌ماند
    """
    
    def __init__(self, config: FTREngineConfig):
        self.config = config
        self.symbol = config.symbol
        self.timeframe = config.timeframe
        
        self.structure_analyzer = StructureAnalyzer(
            config=config.structure_config,
            timeframe=config.timeframe
        )
        self.impulse_detector = ImpulseDetector(config.impulse_config)
        self.base_detector = BaseDetector(config.base_config)
        self.zone_constructor = ZoneConstructor(config.zone_config)
        self.ftb_detector = FTBDetector(config.ftb_config)
        
        self._active_zones: Dict[str, FTRZone] = {}
        self._all_zones: List[FTRZone] = []
        self._ftb_events: List[FTBEvent] = []
        self._processed_breaks: set = set()
        self._pending_breaks: Dict[tuple, StructureBreak] = {}
        
        if config.swing_config:
            self.structure_analyzer.swing_detector.config = config.swing_config
    
    def reset(self):
        """بازنشانی کامل موتور"""
        self.structure_analyzer.reset()
        self.impulse_detector.reset()
        self.base_detector.reset()
        self.zone_constructor.reset()
        self.ftb_detector.reset()
        self._active_zones.clear()
        self._all_zones.clear()
        self._ftb_events.clear()
        self._processed_breaks.clear()
        self._pending_breaks.clear()
    
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
        
        # داده قابل مشاهده: فقط تا current_index
        visible_ohlcv = ohlcv_data[:current_index + 1]
        current_timestamp = visible_ohlcv[current_index]['timestamp']
        
        # ۱. تحلیل ساختار بازار (فقط با داده قابل مشاهده)
        structure_state = self.structure_analyzer.process_bar(visible_ohlcv, current_index)
        result.structure_state = structure_state
        
        # ۲. دریافت Breakهای ثبت‌شده و افزودن به Pending
        recent_breaks = self.structure_analyzer.get_recent_breaks()
        
        for structure_break in recent_breaks:
            break_key = self._make_break_key(structure_break)
            
            # اگر قبلاً پردازش شده، رد شود
            if break_key in self._processed_breaks:
                continue
            
            # اگر Break مربوط به آینده است، رد شود
            if structure_break.break_timestamp > current_timestamp:
                continue
            
            # افزودن به Pending
            if break_key not in self._pending_breaks:
                self._pending_breaks[break_key] = structure_break
        
        # ۳. پردازش Pending Breakها
        for break_key, structure_break in list(self._pending_breaks.items()):
            if break_key in self._processed_breaks:
                del self._pending_breaks[break_key]
                continue
            
            level = structure_break.broken_level
            
            # اگر سطح مصرف شده، رد شود
            if level.is_consumed:
                self._processed_breaks.add(break_key)
                del self._pending_breaks[break_key]
                continue
            
            # یافتن break_index در داده قابل مشاهده
            break_index = self._find_break_index(visible_ohlcv, structure_break.break_timestamp)
            
            if break_index is None:
                continue
            
            # ۴. تشخیص Impulse (فقط با داده قابل مشاهده)
            displacement = self.impulse_detector.detect_impulse(
                visible_ohlcv, break_index, structure_break.direction
            )
            
            if not displacement or not displacement.is_valid:
                # Impulse هنوز کامل نشده — Pending باقی می‌ماند
                continue
            
            # ۵. تشخیص Base (فقط با داده قابل مشاهده)
            base = self.base_detector.detect_base(visible_ohlcv, displacement)
            
            if not base or not base.is_valid:
                # Base هنوز کامل نشده — Pending باقی می‌ماند
                continue
            
            # ۶. ساخت FTR Zone
            zone = self.zone_constructor.construct_zone(
                symbol=self.symbol,
                timeframe=self.timeframe,
                direction=structure_break.direction,
                structure_level=level,
                structure_break=structure_break,
                displacement=displacement,
                base=base,
                current_timestamp=current_timestamp
            )
            
            if zone and self.zone_constructor.validate_zone(zone):
                # ۷. موفقیت — مصرف سطح و علامت‌گذاری Break
                level.is_consumed = True
                self._processed_breaks.add(break_key)
                del self._pending_breaks[break_key]
                
                zone.update_state(FTRZoneState.ACTIVE)
                self._active_zones[zone.zone_id] = zone
                self._all_zones.append(zone)
                self.ftb_detector.add_zone(zone)
                
                result.add_zone(zone)
                result.add_diagnostic(f"FTR zone created: {zone.zone_id}")
        
        # ۸. بررسی FTB و Invalidation برای Zoneهای فعال
        for zone_id, zone in list(self._active_zones.items()):
            if self._check_invalidation(visible_ohlcv, current_index, zone):
                zone.invalidate(current_timestamp)
                del self._active_zones[zone_id]
                self.ftb_detector.remove_zone(zone_id)
                result.add_diagnostic(f"Zone invalidated: {zone_id}")
                continue
            
            ftb_event = self.ftb_detector.check_ftb(visible_ohlcv, current_index, zone)
            
            if ftb_event and ftb_event.is_valid:
                self._ftb_events.append(ftb_event)
                result.add_ftb(ftb_event)
                result.add_diagnostic(f"FTB detected: {zone_id}")
                
                zone.consume(current_timestamp)
                del self._active_zones[zone_id]
                self.ftb_detector.remove_zone(zone_id)
            
            elif ftb_event and not ftb_event.is_valid:
                result.add_diagnostic(f"FTB rejected for zone {zone_id}: {ftb_event.validation_reasons}")
        
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
    
    def get_pending_breaks(self) -> List[StructureBreak]:
        """دریافت Breakهای در انتظار"""
        return list(self._pending_breaks.values())
    
    def _make_break_key(self, structure_break: StructureBreak) -> tuple:
        """ساخت کلید یکتا برای جلوگیری از پردازش تکراری"""
        return (
            structure_break.broken_level.price,
            structure_break.direction,
            structure_break.break_timestamp
        )
    
    def _find_break_index(self, ohlcv_data: List[dict], break_timestamp: int) -> Optional[int]:
        """یافتن ایندکس کندل شکست از timestamp"""
        for i, candle in enumerate(ohlcv_data):
            if candle['timestamp'] == break_timestamp:
                return i
        return None
    
    def _check_invalidation(self, ohlcv_data: List[dict], current_index: int,
                           zone: FTRZone) -> bool:
        """بررسی ابطال Zone"""
        current_candle = ohlcv_data[current_index]
        
        if zone.direction == "LONG":
            if current_candle['close'] < zone.invalidation_level:
                return True
        else:
            if current_candle['close'] > zone.invalidation_level:
                return True
        
        return False