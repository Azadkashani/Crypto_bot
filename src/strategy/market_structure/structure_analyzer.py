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
        self._registered_break_keys: set = set()
    
    def reset(self):
        """بازنشانی وضعیت تحلیلگر"""
        self.swing_detector.reset()
        self._all_swings.clear()
        self._structure_levels.clear()
        self._recent_breaks.clear()
        self._structure_type = StructureType.RANGING
        self._last_break = None
        self._registered_break_keys.clear()
    
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
        """ایجاد سطوح از Swingهای مشابه"""
        if len(swings) < self.config.min_level_strength:
            return
        
        grouped = self._group_swings_by_price(swings)
        
        for price_level, swing_group in grouped.items():
            if len(swing_group) >= self.config.min_level_strength:
                existing_level = self._find_existing_level(price_level, level_type)
                
                if existing_level:
                    existing_level.touch_count += len(swing_group)
                    existing_level.strength_score = len(swing_group)
                else:
                    level = StructureLevel(
                        price=price_level,
                        level_type=level_type,
                        created_timestamp=swing_group[0].timestamp,
                        touch_count=len(swing_group),
                        strength_score=len(swing_group),
                        reference_swings=swing_group.copy()
                    )
                    self._structure_levels.append(level)
    
    def _group_swings_by_price(self, swings: List[SwingPoint]) -> Dict[float, List[SwingPoint]]:
        """گروه‌بندی Swingها بر اساس نزدیکی قیمت"""
        grouped = {}
        tolerance = self.config.level_tolerance_pct
        
        for swing in swings:
            found_group = False
            
            for price_level in list(grouped.keys()):
                if abs(swing.price - price_level) / price_level <= tolerance:
                    grouped[price_level].append(swing)
                    found_group = True
                    break
            
            if not found_group:
                grouped[swing.price] = [swing]
        
        return grouped
    
    def _find_existing_level(self, price: float, level_type: str) -> Optional[StructureLevel]:
        """جستجوی سطح موجود مشابه"""
        tolerance = self.config.level_tolerance_pct
        
        for level in self._structure_levels:
            if level.level_type == level_type:
                if abs(price - level.price) / level.price <= tolerance:
                    return level
        
        return None
    
    def _check_breaks(self, ohlcv_data: List[dict], current_index: int):
        """بررسی شکست‌های ساختاری — شامل کندل‌های قبلی برای تأیید"""
        if not self._structure_levels or current_index < 1:
            return
        
        validation_candles = self.config.break_validation_candles
        
        # بررسی کندل‌های قبلی تا جایی که داده تأیید کافی دارند
        start_check = max(0, current_index - validation_candles)
        
        for check_index in range(start_check, current_index + 1):
            if check_index < 0:
                continue
            
            current_close = ohlcv_data[check_index]['close']
            
            for level in self._structure_levels:
                # فقط سطوحی که قبلاً Break برایشان ثبت نشده بررسی شوند
                if level.is_consumed:
                    continue
                
                break_key = self._make_level_break_key(level)
                
                if break_key in self._registered_break_keys:
                    continue
                
                if level.level_type in ["RESISTANCE", "SUPPLY"]:
                    if current_close > level.price:
                        break_distance = (current_close - level.price) / level.price
                        
                        if break_distance >= self.config.min_break_distance_pct:
                            if self._validate_break(ohlcv_data, check_index, level, "LONG"):
                                self._register_break(
                                    level, "LONG", current_close,
                                    ohlcv_data[check_index]['timestamp']
                                )
                                self._registered_break_keys.add(break_key)
                                # سطح شکسته شده — دیگر برای Break بررسی نشود
                                # اما is_consumed فقط توسط FTREngine پس از ساخت Zone تغییر می‌کند
                                level.last_touched_timestamp = ohlcv_data[check_index]['timestamp']
                
                elif level.level_type in ["SUPPORT", "DEMAND"]:
                    if current_close < level.price:
                        break_distance = (level.price - current_close) / level.price
                        
                        if break_distance >= self.config.min_break_distance_pct:
                            if self._validate_break(ohlcv_data, check_index, level, "SHORT"):
                                self._register_break(
                                    level, "SHORT", current_close,
                                    ohlcv_data[check_index]['timestamp']
                                )
                                self._registered_break_keys.add(break_key)
                                level.last_touched_timestamp = ohlcv_data[check_index]['timestamp']
    
    def _make_level_break_key(self, level: StructureLevel) -> tuple:
        """ساخت کلید یکتا برای سطح جهت جلوگیری از ثبت تکراری Break"""
        return (level.price, level.level_type)
    
    def _validate_break(self, ohlcv_data: List[dict], break_index: int, 
                        level: StructureLevel, direction: str) -> bool:
        """اعتبارسنجی شکست با کندل‌های بعدی"""
        validation_candles = self.config.break_validation_candles
        
        if break_index + validation_candles >= len(ohlcv_data):
            return False
        
        for i in range(break_index + 1, break_index + 1 + validation_candles):
            close = ohlcv_data[i]['close']
            
            if direction == "LONG":
                if close <= level.price:
                    return False
            else:
                if close >= level.price:
                    return False
        
        return True
    
    def _register_break(self, level: StructureLevel, direction: str, 
                       break_price: float, break_timestamp: int):
        """ثبت شکست ساختاری — سطح مصرف نمی‌شود"""
        break_type = self._determine_break_type(direction)
        
        structure_break = StructureBreak(
            break_type=break_type,
            break_price=break_price,
            break_timestamp=break_timestamp,
            broken_level=level,
            direction=direction,
            is_valid=True,
            validation_timestamp=break_timestamp,
            break_strength=1.0
        )
        
        self._recent_breaks.append(structure_break)
        self._last_break = structure_break
        level.last_touched_timestamp = break_timestamp
        # NOTE: is_consumed = True حذف شد
        # سطح فقط پس از ساخت موفق FTR Zone در FTREngine مصرف می‌شود
    
    def _determine_break_type(self, direction: str) -> BreakType:
        """تعیین نوع شکست"""
        if self._structure_type == StructureType.BULLISH and direction == "LONG":
            return BreakType.BOS
        elif self._structure_type == StructureType.BEARISH and direction == "SHORT":
            return BreakType.BOS
        else:
            return BreakType.CHOCH
    
    def _get_last_swing(self, swing_type: SwingType) -> Optional[SwingPoint]:
        """دریافت آخرین Swing از نوع مشخص"""
        for swing in reversed(self._all_swings):
            if swing.swing_type == swing_type:
                return swing
        return None
    
    def _get_previous_swing(self, swing_type: SwingType) -> Optional[SwingPoint]:
        """دریافت Swing قبلی از نوع مشخص"""
        found_first = False
        
        for swing in reversed(self._all_swings):
            if swing.swing_type == swing_type:
                if found_first:
                    return swing
                found_first = True
        
        return None