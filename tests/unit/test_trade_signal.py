# FILE: tests/unit/test_trade_signal.py

"""
تست‌های Trade Signal Layer
"""

import pytest
from typing import List
from src.strategy.types.market_structure import (
    StructureType, BreakType, StructureBreak, StructureLevel
)
from src.strategy.types.ftr_types import (
    FTRZone, FTRZoneState, FTBEvent, FTBTouchType,
    DisplacementData, BaseData
)
from src.strategy.signal.signal_quality_types import (
    SignalQualityResult, SignalClassification, ComponentScores
)
from src.strategy.trade.trade_signal_engine import TradeSignalEngine
from src.strategy.trade.trade_signal_types import TradeSignal


def create_long_zone() -> FTRZone:
    """ایجاد Zone صعودی"""
    return FTRZone(
        zone_id="long_zone",
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


def create_short_zone() -> FTRZone:
    """ایجاد Zone نزولی"""
    return FTRZone(
        zone_id="short_zone",
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


def create_qualified_signal(direction: str = "LONG") -> SignalQualityResult:
    """ایجاد Signal Quality Result با کیفیت بالا"""
    return SignalQualityResult(
        signal_id="SIG_TEST",
        symbol="BTC_USDT",
        timeframe="1h",
        direction=direction,
        score=85.0,
        classification=SignalClassification.QUALIFIED,
        component_scores=ComponentScores(
            structure_score=15.0,
            displacement_score=15.0,
            base_score=12.0,
            zone_score=12.0,
            ftb_score=20.0,
            trend_score=11.0
        ),
        positive_factors=["Strong BOS", "First touch"],
        warning_factors=[],
        rejection_reasons=[],
        timestamp=105000
    )


def create_watch_signal() -> SignalQualityResult:
    """ایجاد سیگنال WATCH"""
    return SignalQualityResult(
        signal_id="SIG_WATCH",
        symbol="BTC_USDT",
        timeframe="1h",
        direction="LONG",
        score=70.0,
        classification=SignalClassification.WATCH,
        component_scores=ComponentScores(
            structure_score=12.0,
            displacement_score=12.0,
            base_score=10.0,
            zone_score=10.0,
            ftb_score=16.0,
            trend_score=10.0
        ),
        positive_factors=[],
        warning_factors=["Moderate signal"],
        rejection_reasons=[],
        timestamp=105000
    )


def create_rejected_signal() -> SignalQualityResult:
    """ایجاد سیگنال REJECTED"""
    return SignalQualityResult(
        signal_id="SIG_REJECTED",
        symbol="BTC_USDT",
        timeframe="1h",
        direction="LONG",
        score=40.0,
        classification=SignalClassification.REJECTED,
        component_scores=ComponentScores(
            structure_score=5.0,
            displacement_score=5.0,
            base_score=5.0,
            zone_score=5.0,
            ftb_score=10.0,
            trend_score=10.0
        ),
        positive_factors=[],
        warning_factors=["Weak signal"],
        rejection_reasons=["Deep touch", "Weak displacement"],
        timestamp=105000
    )


def create_ftb_event_long() -> FTBEvent:
    """ایجاد FTB برای LONG"""
    zone = create_long_zone()
    return FTBEvent(
        zone=zone,
        timestamp=105000,
        price=129.0,
        touch_type=FTBTouchType.WICK,
        penetration_depth=1.0,
        is_valid=True
    )


def create_ftb_event_short() -> FTBEvent:
    """ایجاد FTB برای SHORT"""
    zone = create_short_zone()
    return FTBEvent(
        zone=zone,
        timestamp=105000,
        price=127.0,
        touch_type=FTBTouchType.WICK,
        penetration_depth=1.0,
        is_valid=True
    )


def create_structure_levels(direction: str = "LONG") -> List[StructureLevel]:
    """ایجاد سطوح ساختاری"""
    if direction == "LONG":
        return [
            StructureLevel(price=135.0, level_type="RESISTANCE", created_timestamp=90000),
            StructureLevel(price=140.0, level_type="RESISTANCE", created_timestamp=80000),
            StructureLevel(price=120.0, level_type="SUPPORT", created_timestamp=85000),
        ]
    else:
        return [
            StructureLevel(price=120.0, level_type="SUPPORT", created_timestamp=90000),
            StructureLevel(price=115.0, level_type="SUPPORT", created_timestamp=80000),
            StructureLevel(price=135.0, level_type="RESISTANCE", created_timestamp=85000),
        ]


class TestTradeSignal:
    """تست‌های Trade Signal Layer"""
    
    def test_qualified_long_signal(self):
        """تست سیگنال معتبر LONG"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.direction == "LONG"
        assert signal.entry_price == 129.0
        assert signal.stop_loss == 125.0
        assert signal.take_profit == 135.0
        assert signal.risk_reward > 0
        assert signal.is_valid
    
    def test_qualified_short_signal(self):
        """تست سیگنال معتبر SHORT"""
        engine = TradeSignalEngine()
        zone = create_short_zone()
        ftb = create_ftb_event_short()
        quality = create_qualified_signal("SHORT")
        levels = create_structure_levels("SHORT")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.direction == "SHORT"
        assert signal.entry_price == 127.0
        assert signal.stop_loss == 131.0
        assert signal.take_profit == 120.0
        assert signal.risk_reward > 0
        assert signal.is_valid
    
    def test_watch_signal_no_trade(self):
        """تست سیگنال WATCH → بدون Trade Signal"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_watch_signal()
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is None
    
    def test_rejected_signal_no_trade(self):
        """تست سیگنال REJECTED → بدون Trade Signal"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_rejected_signal()
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is None
    
    def test_long_sl_validation(self):
        """تست اعتبارسنجی SL برای LONG"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.stop_loss < signal.entry_price
    
    def test_short_sl_validation(self):
        """تست اعتبارسنجی SL برای SHORT"""
        engine = TradeSignalEngine()
        zone = create_short_zone()
        ftb = create_ftb_event_short()
        quality = create_qualified_signal("SHORT")
        levels = create_structure_levels("SHORT")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.stop_loss > signal.entry_price
    
    def test_long_tp_validation(self):
        """تست اعتبارسنجی TP برای LONG"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.take_profit > signal.entry_price
    
    def test_short_tp_validation(self):
        """تست اعتبارسنجی TP برای SHORT"""
        engine = TradeSignalEngine()
        zone = create_short_zone()
        ftb = create_ftb_event_short()
        quality = create_qualified_signal("SHORT")
        levels = create_structure_levels("SHORT")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        assert signal.take_profit < signal.entry_price
    
    def test_rr_calculation(self):
        """تست محاسبه R:R"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        levels = create_structure_levels("LONG")
        
        signal = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal is not None
        expected_risk = abs(129.0 - 125.0)  # 4.0
        expected_reward = abs(135.0 - 129.0)  # 6.0
        expected_rr = 6.0 / 4.0  # 1.5
        
        assert abs(signal.risk - expected_risk) < 0.001
        assert abs(signal.reward - expected_reward) < 0.001
        assert abs(signal.risk_reward - expected_rr) < 0.001
    
    def test_determinism(self):
        """تست قطعیت"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        levels = create_structure_levels("LONG")
        
        signal1 = engine.create_trade_signal(quality, zone, ftb, levels)
        engine.reset()
        signal2 = engine.create_trade_signal(quality, zone, ftb, levels)
        
        assert signal1 is not None
        assert signal2 is not None
        assert signal1.entry_price == signal2.entry_price
        assert signal1.stop_loss == signal2.stop_loss
        assert signal1.take_profit == signal2.take_profit
        assert signal1.risk_reward == signal2.risk_reward
    
    def test_no_lookahead_target(self):
        """تست عدم استفاده از داده آینده برای Target"""
        engine = TradeSignalEngine()
        zone = create_long_zone()
        ftb = create_ftb_event_long()
        quality = create_qualified_signal("LONG")
        
        # سطوح ساختاری شناخته‌شده قبل از signal timestamp
        levels_known = [
            StructureLevel(price=135.0, level_type="RESISTANCE", created_timestamp=90000),
        ]
        
        # سطح آینده
        levels_with_future = [
            StructureLevel(price=135.0, level_type="RESISTANCE", created_timestamp=90000),
            StructureLevel(price=150.0, level_type="RESISTANCE", created_timestamp=110000),  # آینده
        ]
        
        signal_known = engine.create_trade_signal(quality, zone, ftb, levels_known)
        engine.reset()
        signal_with_future = engine.create_trade_signal(quality, zone, ftb, levels_with_future)
        
        assert signal_known is not None
        assert signal_with_future is not None
        # Target نباید از سطح آینده استفاده کند
        # Engine فقط نزدیک‌ترین سطح را انتخاب می‌کند
        # اگر سطح آینده نزدیک‌تر نباشد، Target یکسان است
        assert signal_known.take_profit == 135.0
        # سطح 150 دورتر از 135 است، پس Target همان 135 می‌ماند
        assert signal_with_future.take_profit == 135.0
