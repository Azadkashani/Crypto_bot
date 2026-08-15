# FILE: tests/unit/test_signal_quality.py

"""
تست‌های Signal Quality Layer
"""

import pytest
from typing import List, Dict, Any
from src.strategy.types.market_structure import (
    StructureType, BreakType, StructureBreak, StructureLevel
)
from src.strategy.types.ftr_types import (
    FTRZone, FTRZoneState, FTBEvent, FTBTouchType,
    DisplacementData, BaseData
)
from src.strategy.signal.signal_quality_engine import SignalQualityEngine
from src.strategy.signal.signal_quality_types import (
    SignalQualityConfig, SignalClassification
)


def create_test_zone(direction: str = "LONG") -> FTRZone:
    """ایجاد Zone تستی"""
    if direction == "LONG":
        zone = FTRZone(
            zone_id="test_long_zone",
            symbol="BTC_USDT",
            timeframe="1h",
            direction="LONG",
            zone_high=130.0,
            zone_low=126.0,
            zone_midpoint=128.0,
            created_timestamp=100000,
            invalidation_level=125.0,
            state=FTRZoneState.FIRST_TOUCH,
            first_touch_timestamp=105000,
            first_touch_price=129.0,
            first_touch_type=FTBTouchType.WICK,
            touch_count=1,
            displacement=DisplacementData(
                start_price=108.0,
                end_price=126.0,
                start_timestamp=95000,
                end_timestamp=100000,
                direction="LONG",
                candle_count=5,
                strength_score=0.8,
                start_index=25,
                end_index=35
            ),
            base=BaseData(
                high=130.0,
                low=126.0,
                start_timestamp=100000,
                end_timestamp=102000,
                start_index=35,
                end_index=42,
                quality_score=0.7,
                compression_ratio=0.5
            )
        )
    else:
        zone = FTRZone(
            zone_id="test_short_zone",
            symbol="BTC_USDT",
            timeframe="1h",
            direction="SHORT",
            zone_high=130.0,
            zone_low=126.0,
            zone_midpoint=128.0,
            created_timestamp=100000,
            invalidation_level=131.0,
            state=FTRZoneState.FIRST_TOUCH,
            first_touch_timestamp=105000,
            first_touch_price=127.0,
            first_touch_type=FTBTouchType.WICK,
            touch_count=1,
            displacement=DisplacementData(
                start_price=150.0,
                end_price=126.0,
                start_timestamp=95000,
                end_timestamp=100000,
                direction="SHORT",
                candle_count=5,
                strength_score=0.8,
                start_index=25,
                end_index=35
            ),
            base=BaseData(
                high=130.0,
                low=126.0,
                start_timestamp=100000,
                end_timestamp=102000,
                start_index=35,
                end_index=42,
                quality_score=0.7,
                compression_ratio=0.5
            )
        )
    
    return zone


def create_structure_break(direction: str = "LONG") -> StructureBreak:
    """ایجاد StructureBreak تستی"""
    level = StructureLevel(
        price=108.0,
        level_type="RESISTANCE" if direction == "LONG" else "SUPPORT",
        created_timestamp=90000,
        strength_score=2.0
    )
    
    return StructureBreak(
        break_type=BreakType.BOS,
        break_price=110.0,
        break_timestamp=90000,
        broken_level=level,
        direction=direction,
        is_valid=True,
        validation_timestamp=90000,
        break_strength=0.8
    )


def create_ftb_event(zone: FTRZone, touch_type: FTBTouchType = FTBTouchType.WICK,
                     touch_price: float = None) -> FTBEvent:
    """ایجاد FTB Event تستی"""
    if touch_price is None:
        touch_price = zone.zone_high - 0.5 if zone.direction == "LONG" else zone.zone_low + 0.5
    
    return FTBEvent(
        zone=zone,
        timestamp=105000,
        price=touch_price,
        touch_type=touch_type,
        is_valid=True,
        penetration_depth=abs(touch_price - zone.zone_high if zone.direction == "LONG" else zone.zone_low - touch_price)
    )


class TestSignalQuality:
    """تست‌های Signal Quality Engine"""
    
    def get_default_config(self) -> SignalQualityConfig:
        return SignalQualityConfig(
            structure_weight=20.0,
            displacement_weight=20.0,
            base_weight=15.0,
            zone_weight=15.0,
            ftb_weight=20.0,
            trend_weight=10.0,
            min_qualified_score=80.0,
            min_watch_score=60.0
        )
    
    def test_high_quality_long_signal(self):
        """تست سیگنال با کیفیت بالا — LONG"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        structure_break = create_structure_break("LONG")
        ftb = create_ftb_event(zone, FTBTouchType.WICK, 129.0)
        
        result = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000,
            trend_direction="LONG"
        )
        
        assert result.classification == SignalClassification.QUALIFIED
        assert result.score >= 80.0
        assert result.direction == "LONG"
        assert len(result.positive_factors) > 0
    
    def test_high_quality_short_signal(self):
        """تست سیگنال با کیفیت بالا — SHORT"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("SHORT")
        structure_break = create_structure_break("SHORT")
        ftb = create_ftb_event(zone, FTBTouchType.WICK, 127.0)
        
        result = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.BEARISH,
            timestamp=105000,
            trend_direction="SHORT"
        )
        
        assert result.classification == SignalClassification.QUALIFIED
        assert result.score >= 80.0
        assert result.direction == "SHORT"
    
    def test_weak_signal_rejected(self):
        """تست سیگنال ضعیف — Rejected"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        # تضعیف Zone
        zone.displacement = None
        zone.base = None
        zone.state = FTRZoneState.ACTIVE
        zone.first_touch_timestamp = None
        
        structure_break = create_structure_break("LONG")
        structure_break.break_type = BreakType.CHOCH
        structure_break.break_strength = 0.2
        
        ftb = create_ftb_event(zone, FTBTouchType.PENETRATION, zone.zone_low + 0.5)
        ftb.is_valid = False
        
        result = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.RANGING,
            timestamp=105000,
            trend_direction="SHORT"  # خلاف جهت
        )
        
        assert result.classification == SignalClassification.REJECTED
        assert result.score < 60.0
    
    def test_watch_signal(self):
        """تست سیگنال متوسط — Watch"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        # تضعیف نسبی
        zone.displacement.strength_score = 0.4
        zone.base.quality_score = 0.3
        
        structure_break = create_structure_break("LONG")
        ftb = create_ftb_event(zone, FTBTouchType.CLOSE, zone.zone_midpoint)
        
        result = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000,
            trend_direction=None  # بدون داده روند
        )
        
        assert result.classification in [SignalClassification.WATCH, SignalClassification.REJECTED]
        assert result.score < 80.0
    
    def test_trend_conflict_reduces_score(self):
        """تست کاهش امتیاز با روند مخالف"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        structure_break = create_structure_break("LONG")
        ftb = create_ftb_event(zone, FTBTouchType.WICK, 129.0)
        
        result_aligned = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000,
            trend_direction="LONG"
        )
        
        result_conflicted = engine.evaluate_signal(
            symbol="BTC_USDT",
            timeframe="1h",
            zone=zone,
            ftb_event=ftb,
            structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000,
            trend_direction="SHORT"
        )
        
        assert result_aligned.score > result_conflicted.score
    
    def test_determinism(self):
        """تست قطعیت — داده یکسان نتیجه یکسان"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        structure_break = create_structure_break("LONG")
        ftb = create_ftb_event(zone, FTBTouchType.WICK, 129.0)
        
        result1 = engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=ftb, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        engine.reset()
        
        result2 = engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=ftb, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        assert result1.score == result2.score
        assert result1.classification == result2.classification
    
    def test_deep_touch_reduces_ftb_score(self):
        """تست کاهش امتیاز FTB با نفوذ عمیق"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        structure_break = create_structure_break("LONG")
        
        shallow_touch = create_ftb_event(zone, FTBTouchType.WICK, zone.zone_high - 0.3)
        deep_touch = create_ftb_event(zone, FTBTouchType.PENETRATION, zone.zone_low + 0.3)
        
        result_shallow = engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=shallow_touch, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        result_deep = engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=deep_touch, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        assert result_shallow.component_scores.ftb_score > result_deep.component_scores.ftb_score
    
    def test_reset(self):
        """تست Reset"""
        engine = SignalQualityEngine(self.get_default_config())
        zone = create_test_zone("LONG")
        structure_break = create_structure_break("LONG")
        ftb = create_ftb_event(zone, FTBTouchType.WICK, 129.0)
        
        engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=ftb, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        engine.reset()
        
        engine.evaluate_signal(
            symbol="BTC_USDT", timeframe="1h", zone=zone,
            ftb_event=ftb, structure_break=structure_break,
            market_structure_type=StructureType.BULLISH,
            timestamp=105000, trend_direction="LONG"
        )
        
        # شمارنده باید reset شده باشد
        assert engine._signal_counter == 1
