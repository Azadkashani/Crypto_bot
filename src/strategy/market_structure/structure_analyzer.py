# FILE: src/strategy/market_structure/structure_analyzer.py

"""
تحلیل ساختار بازار بر اساس Swing Points
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import (
    SwingPoint, SwingType, StructureLevel, StructureBreak,
    MarketStructureState, StructureType, BreakType
)
from .swing_detector import SwingDetector, SwingDetectorConfig


@dataclass
class StructureAnalyzerConfig:
    """پیکربندی تحلیل ساختار"""
    min_level_strength: int = 2
    level_tolerance_pct: float = 0.0005
    break_validation_candles: int = 1
    min_break_distance_pct: float = 0.001
    
    def validate(self) -> List[str]:
        errors = []
        if self.min_level_strength < 1:
            errors.append("min_level_strength must be >= 1")
        if self.level_tolerance_pct <= 0:
            errors.append("level_tolerance_pct must be > 0")
        if self.break_validation_candles < 1:
            errors.append("break_validation_candles must be >= 1")
        if self.min_break_distance_pct <= 0:
            errors.append("min_break_distance_pct must be > 0")
        return errors


class StructureAnalyzer:
    """
    تحلیل ساختار بازار با استفاده از Swing Points
    """
    
    def __init__(self, config: Optional[StructureAnalyzerConfig] = None, timeframe: str = ""):
        self.config = config or StructureAnalyzerConfig()
        self.swing_detector = SwingDetector()
        self.timeframe = timeframe
        self._all_swings: List[SwingPoint] = []
        self._structure_levels: List[StructureLevel] = []
        self._recent_breaks: List[StructureBreak] = []
        self._structure_type: StructureType = StructureType.RANGING
        self._last_break: Optional[StructureBreak] = None
    
    def reset(self):
        """بازنشانی وضعیت تحلیلگر"""
        self.swing_detector.reset()
        self._all_swings.clear()
        self._structure_levels.clear()
        self._recent_breaks.clear()
        self._structure_type = StructureType.RANGING
        self._last_break = None
    
    def process_bar(self, ohlcv_data: List[dict], current_index: int) -> MarketStructureState:
        """پردازش کندل جاری و به‌روزرسانی ساختار بازار"""
        new_swings = self.swing_detector.process_bar(ohlcv_data, current_index)
        self._all_swings.extend(new_swings)
        
        if new_swings:
            self._update_structure(new_swings)
        
        self._check_breaks(ohlcv_data, current_index)
        
        return self._build_market_structure_state()
    
    def get_structure_levels(self) -> List[StructureLevel]:
        """دریافت سطوح ساختاری"""
        return self._structure_levels.copy()
    
    def get_recent_breaks(self) -> List[StructureBreak]:
        """دریافت شکست‌های ثبت‌شده"""
        return self._recent_breaks.copy()
    
    def _build_market_structure_state(self) -> MarketStructureState:
        """ساخت وضعیت فعلی ساختار بازار"""
        last_high = self._get_last_swing(SwingType.HIGH)
        last_low = self._get_last_swing(SwingType.LOW)
        
        return MarketStructureState(
            timeframe=self.timeframe,
            structure_type=self._structure_type,
            current_swing_high=last_high,
            current_swing_low=last_low,
            last_break=self._last_break,
            swing_points=self._all_swings.copy(),
            structure_levels=self._structure_levels.copy()
        )
    
    def _update_structure(self, new_swings: List[SwingPoint]):
        """به‌روزرسانی ساختار با Swingهای جدید"""
        if len(self._all_swings) < 2:
            return
        
        last_swing_high = self._get_last_swing(SwingType.HIGH)
        last_swing_low = self._get_last_swing(SwingType.LOW)
        
        if last_swing_high and last_swing_low:
            prev_high = self._get_previous_swing(SwingType.HIGH)
            prev_low = self._get_previous_swing(SwingType.LOW)
            
            if prev_high and prev_low:
                if last_swing_high.price > prev_high.price and last_swing_low.price > prev_low.price:
                    self._update_structure_type(StructureType.BULLISH)
                elif last_swing_high.price < prev_high.price and last_swing_low.price < prev_low.price:
                    self._update_structure_type(StructureType.BEARISH)
                else:
                    self._update_structure_type(StructureType.RANGING)
        
        self._update_structure_levels()
    
    def _update_structure_type(self, new_type: StructureType):
        """به‌روزرسانی نوع ساختار"""
        if self._structure_type != new_type:
            old_type = self._structure_type
            self._structure_type = new_type
            
            if old_type == StructureType.BULLISH and new_type == StructureType.BEARISH:
                self._register_choch("BEARISH")
            elif old_type == StructureType.BEARISH and new_type == StructureType.BULLISH:
                self._register_choch("BULLISH")
    
    def _register_choch(self, direction: str):
        """ثبت Change of Character"""
        last_swing = self._get_last_swing(
            SwingType.LOW if direction == "BEARISH" else SwingType.HIGH
        )
        
        if last_swing:
            level = StructureLevel(
                price=last_swing.price,
                level_type="CHOCH",
                created_timestamp=last_swing.timestamp,
                strength_score=2.0
            )
            self._structure_levels.append(level)
    
    def _update_structure_levels(self):
        """به‌روزرسانی سطوح ساختاری از Swingها"""
        swing_highs = [s for s in self._all_swings if s.swing_type == SwingType.HIGH]
        self._create_levels_from_swings(swing_highs, "RESISTANCE")
        
        swing_lows = [s for s in self._all_swings if s.swing_type == SwingType.LOW]
        self._create_levels_from_swings(swing_lows, "SUPPORT")
    
    def _create_levels_from_swings(self, swings: List[SwingPoint], level_type: str):
        """ایجاد سط