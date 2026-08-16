# FILE: src/strategy/ftr/ftr_engine.py

"""
موتور اصلی تشخیص FTR — با Pending Base Tracking
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


@dataclass
class PendingBaseState:
    """وضعیت Pending Base — برای پیگیری Base در چند کندل"""
    break_key: tuple
    structure_break: StructureBreak
    displacement: DisplacementData
    start_index: int  # اولین کندل Base
    created_index: int  # کندلی که Impulse کامل شد
    last_checked_index: int = 0
    is_complete: bool = False
    is_invalidated: bool = False
    invalid_reason: str = ""


class FTREngine:
    """
    موتور اصلی تشخیص FTR
    
    Pipeline:
    Structure Break → Pending Impulse → Pending Base → FTR Zone → FTB
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
        self._pending_bases: Dict[tuple, PendingBaseState] = {}
        self._zone_creation_indices: Dict[str, int] = {}
        
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
        self._pending_bases.clear()
        self._zone_creation_indices.clear()
    
    def process_bar(self, ohlcv_data: List[dict], current_index: int) -> FTRDetectionResult:
        """
        پردازش کندل جاری و تشخیص FTR
        """
        result = FTRDetectionResult()
        
        if current_index < 2:
            return result
        
        visible_ohlcv = ohlcv_data[:current_index + 1]
        current_timestamp = visible_ohlcv[current_index]['timestamp']
        
        # ۱. تحلیل ساختار بازار
        structure_state = self.structure_analyzer.process_bar(visible_ohlcv, current_index)
        result.structure_state = structure_state
        
        # ۲. دریافت Breakهای جدید
        recent_breaks = self.structure_analyzer.get_recent_breaks()
        
        for structure_break in recent_breaks:
            break_key = self._make_break_key(structure_break)
            
            if break_key in self._processed_breaks:
                continue
            
            if structure_break.break_timestamp > current_timestamp:
                continue
            
            if break_key not in self._pending_breaks:
                self._pending_breaks[break_key] = structure_break
        
        # ۳. پردازش Pending Breaks — تلاش برای Impulse
        for break_key, structure_break in list(self._pending_breaks.items()):
            if break_key in self._processed_breaks:
                del self._pending_breaks[break_key]
                continue
            
            level = structure_break.broken_level
            
            if level.is_consumed:
                self._processed_breaks.add(break_key)
                del self._pending_breaks[break_key]
                continue
            
            break_index = self._find_break_index(visible_ohlcv, structure_break.break_timestamp)
            
            if break_index is None:
                continue
            
            # تلاش برای Impulse
            displacement = self.impulse_detector.detect_impulse(
                visible_ohlcv, break_index, structure_break.direction
            )
            
            if not displacement or not displacement.is_valid:
                continue
            
            # Impulse معتبر — ایجاد Pending Base
            if break_key not in self._pending_bases:
                self._pending_bases[break_key] = PendingBaseState(
                    break_key=break_key,
                    structure_break=structure_break,
                    displacement=displacement,
                    start_index=displacement.end_index + 1,
                    created_index=current_index,
                    last_checked_index=current_index,
                )
        
        # ۴. پردازش Pending Bases — تلاش برای تکمیل Base
        for break_key, pending_base in list(self._pending_bases.items()):
            if break_key in self._processed_breaks:
                del self._pending_bases[break_key]
                continue
            
            # جلوگیری از بررسی تکراری در همان کندل
            if pending_base.last_checked_index >= current_index:
                continue
            
            pending_base.last_checked_index = current_index
            
            structure_break = pending_base.structure_break
            displacement = pending_base.displacement
            level = structure_break.broken_level
            
            # بررسی Base با داده قابل مشاهده
            base = self.base_detector.detect_base(visible_ohlcv, displacement)
            
            if base is None or not base.is_valid:
                # Base هنوز کامل نشده — بررسی انقضا
                if current_index - pending_base.created_index > 30:
                    pending_base.is_invalidated = True
                    pending_base.invalid_reason = "BASE_TIMEOUT"
                    del self._pending_bases[break_key]
                continue
            
            # Base معتبر — ساخت Zone
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
                # موفقیت
                level.is_consumed = True
                self._processed_breaks.add(break_key)
                del self._pending_bases[break_key]
                
                if break_key in self._pending_breaks:
                    del self._pending_breaks[break_key]
                
                zone.update_state(FTRZoneState.ACTIVE)
                self._active_zones[zone.zone_id] = zone
                self._all_zones.append(zone)
                self.ftb_detector.add_zone(zone)
                self._zone_creation_indices[zone.zone_id] = current_index
                
                result.add_zone(zone)
                result.add_diagnostic(f"FTR zone created: {zone.zone_id}")
            else:
                pending_base.is_invalidated = True
                pending_base.invalid_reason = "ZONE_INVALID"
                del self._pending_bases[break_key]
        
        # ۵. بررسی FTB و Invalidation
        for zone_id, zone in list(self._active_zones.items()):
            creation_index = self._zone_creation_indices.get(zone_id, -1)
            if creation_index >= current_index:
                continue
            
            if self._check_invalidation(visible_ohlcv, current_index, zone):
                zone.invalidate(current_timestamp)
                del self._active_zones[zone_id]
                self.ftb_detector.remove_zone(zone_id)
                del self._zone_creation_indices[zone_id]
                result.add_diagnostic(f"Zone invalidated: {zone_id}")
                continue
            
            ftb_event = self.ftb_detector.check_ftb(visible_ohlcv, current_index, zone)
            
            if ftb_event and ftb_event.is_valid:
                self._ftb_events.append(ftb_event)
                result.add_ftb(ftb_event)
                
                zone.consume(current_timestamp)
                del self._active_zones[zone_id]
                self.ftb_detector.remove_zone(zone_id)
                del self._zone_creation_indices[zone_id]
        
        return result
    
    def get_active_zones(self) -> List[FTRZone]:
        return list(self._active_zones.values())
    
    def get_all_zones(self) -> List[FTRZone]:
        return self._all_zones.copy()
    
    def get_ftb_events(self) -> List[FTBEvent]:
        return self._ftb_events.copy()
    
    def get_pending_breaks(self) -> List[StructureBreak]:
        return list(self._pending_breaks.values())
    
    def get_pending_bases(self) -> int:
        return len(self._pending_bases)
    
    def _make_break_key(self, structure_break: StructureBreak) -> tuple:
        return (
            structure_break.broken_level.price,
            structure_break.direction,
            structure_break.break_timestamp
        )
    
    def _find_break_index(self, ohlcv_data: List[dict], break_timestamp: int) -> Optional[int]:
        for i, candle in enumerate(ohlcv_data):
            if candle['timestamp'] == break_timestamp:
                return i
        return None
    
    def _check_invalidation(self, ohlcv_data: List[dict], current_index: int,
                           zone: FTRZone) -> bool:
        current_candle = ohlcv_data[current_index]
        
        if zone.direction == "LONG":
            if current_candle['close'] < zone.invalidation_level:
                return True
        else:
            if current_candle['close'] > zone.invalidation_level:
                return True
        
        return False
