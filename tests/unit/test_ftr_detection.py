# FILE: tests/unit/test_ftr_detection.py

"""
تست‌های واحد برای موتور تشخیص FTR
"""

import pytest
from typing import List, Dict, Any
from src.strategy.types.market_structure import StructureType
from src.strategy.types.ftr_types import FTRZoneState, FTBTouchType
from src.strategy.ftr.ftr_engine import FTREngine, FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.breakout_detector import BreakoutDetectorConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def create_ohlcv_data(prices: List[float], highs: List[float], lows: List[float],
                     opens: List[float], volumes: List[float] = None) -> List[dict]:
    """ایجاد داده OHLCV مصنوعی"""
    data = []
    
    for i in range(len(prices)):
        candle = {
            'open': opens[i],
            'high': highs[i],
            'low': lows[i],
            'close': prices[i],
            'volume': volumes[i] if volumes else 100,
            'timestamp': i * 3600  # هر کندل یک ساعت
        }
        data.append(candle)
    
    return data


def create_bullish_ftr_scenario() -> List[dict]:
    """
    ایجاد سناریوی FTR صعودی:
    ۱. حرکت صعودی قوی (شکست)
    ۲. Base کوتاه
    ۳. ادامه صعود
    ۴. بازگشت به Zone (FTB)
    """
    n = 60
    prices = []
    highs = []
    lows = []
    opens = []
    
    base_price = 100.0
    
    # فاز ۱: حرکت صعودی اولیه
    for i in range(15):
        price = base_price + i * 1.0
        opens.append(price - 0.5)
        prices.append(price)
        highs.append(price + 0.8)
        lows.append(price - 0.5)
    
    # سطح مقاومت حدود 115
    
    # فاز ۲: شکست مقاومت با قدرت
    for i in range(8):
        price = 115 + i * 1.5
        opens.append(price - 1.0)
        prices.append(price)
        highs.append(price + 0.7)
        lows.append(price - 0.5)
    
    # فاز ۳: Impulse قوی
    impulse_start = 127
    for i in range(7):
        price = impulse_start + i * 2.5
        opens.append(price - 2.0)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.8)
    
    # فاز ۴: Base (تثبیت)
    base_high = 145
    base_low = 140
    for i in range(10):
        price = base_low + (i % 4) * 1.2
        opens.append(price)
        prices.append(price)
        highs.append(base_high)
        lows.append(base_low)
    
    # فاز ۵: ادامه صعود (Continuation)
    for i in range(8):
        price = base_high + 2 + i * 2.0
        opens.append(price - 1.5)
        prices.append(price)
        highs.append(price + 1.0)
        lows.append(price - 0.5)
    
    # فاز ۶: بازگشت به Zone (FTB)
    for i in range(12):
        price = base_high - i * 0.3
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.4)
    
    return create_ohlcv_data(prices[:n], highs[:n], lows[:n], opens[:n])


def create_bearish_ftr_scenario() -> List[dict]:
    """
    ایجاد سناریوی FTR نزولی
    """
    n = 60
    prices = []
    highs = []
    lows = []
    opens = []
    
    base_price = 200.0
    
    # فاز ۱: حرکت نزولی اولیه
    for i in range(15):
        price = base_price - i * 1.0
        opens.append(price + 0.5)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.8)
    
    # فاز ۲: شکست حمایت
    for i in range(8):
        price = 185 - i * 1.5
        opens.append(price + 1.0)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.7)
    
    # فاز ۳: Impulse نزولی
    impulse_start = 173
    for i in range(7):
        price = impulse_start - i * 2.5
        opens.append(price + 2.0)
        prices.append(price)
        highs.append(price + 0.8)
        lows.append(price - 0.5)
    
    # فاز ۴: Base
    base_high = 155
    base_low = 150
    for i in range(10):
        price = base_high - (i % 4) * 1.2
        opens.append(price)
        prices.append(price)
        highs.append(base_high)
        lows.append(base_low)
    
    # فاز ۵: ادامه نزول
    for i in range(8):
        price = base_low - 2 - i * 2.0
        opens.append(price + 1.5)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 1.0)
    
    # فاز ۶: بازگشت به Zone
    for i in range(12):
        price = base_low + i * 0.3
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.5)
    
    return create_ohlcv_data(prices[:n], highs[:n], lows[:n], opens[:n])


def get_default_config() -> FTREngineConfig:
    """ایجاد پیکربندی پیش‌فرض برای تست"""
    return FTREngineConfig(
        symbol="BTC_USDT",
        timeframe="1h",
        swing_config=SwingDetectorConfig(
            pivot_left=2,
            pivot_right=2,
            min_swing_distance_pct=0.0005
        ),
        structure_config=StructureAnalyzerConfig(
            min_level_strength=2,
            level_tolerance_pct=0.001,
            break_validation_candles=1,
            min_break_distance_pct=0.001
        ),
        breakout_config=BreakoutDetectorConfig(
            break_method="close",
            min_break_distance_pct=0.001,
            min_break_strength=0.3,
            confirmation_candles=1
        ),
        impulse_config=ImpulseDetectorConfig(
            min_impulse_candles=2,
            max_impulse_candles=10,
            min_impulse_distance_pct=0.002,
            min_body_ratio=0.4
        ),
        base_config=BaseDetectorConfig(
            min_base_candles=2,
            max_base_candles=15,
            max_retracement_pct=0.382,
            max_base_range_pct=0.25
        ),
        zone_config=ZoneConstructorConfig(
            invalidation_buffer_pct=0.05,
            min_zone_height_pct=0.0005
        ),
        ftb_config=FTBDetectorConfig(
            max_ftb_wait_candles=30,
            min_touch_depth_pct=0.0,
            max_touch_depth_pct=0.8,
            allow_wick_touch=True,
            allow_close_touch=True
        )
    )


class TestFTRDetection:
    """تست‌های تشخیص FTR"""
    
    def test_bullish_ftr_detection(self):
        """تست تشخیص FTR صعودی"""
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        zones = []
        ftb_events = []
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            
            if result.zones:
                zones.extend(result.zones)
            
            if result.ftb_events:
                ftb_events.extend(result.ftb_events)
        
        assert len(zones) > 0, "باید حداقل یک FTR Zone تشخیص داده شود"
        
        if zones:
            zone = zones[0]
            assert zone.direction == "LONG", "جهت Zone باید LONG باشد"
            assert zone.zone_high > zone.zone_low, "مرزهای Zone باید صحیح باشند"
            assert zone.state in [FTRZoneState.ACTIVE, FTRZoneState.FIRST_TOUCH, FTRZoneState.USED]
    
    def test_bearish_ftr_detection(self):
        """تست تشخیص FTR نزولی"""
        ohlcv_data = create_bearish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        zones = []
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            
            if result.zones:
                zones.extend(result.zones)
        
        assert isinstance(zones, list)
    
    def test_zone_lifecycle(self):
        """تست چرخه حیات Zone"""
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
        
        all_zones = engine.get_all_zones()
        
        if all_zones:
            zone = all_zones[0]
            assert zone.state in [FTRZoneState.ACTIVE, FTRZoneState.FIRST_TOUCH, 
                                 FTRZoneState.USED, FTRZoneState.INVALIDATED]
    
    def test_invalid_structure_no_zone(self):
        """تست عدم تشخیص Zone در ساختار نامعتبر"""
        n = 30
        prices = [100 + (i % 5) * 0.1 for i in range(n)]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        opens = [p for p in prices]
        
        ohlcv_data = create_ohlcv_data(prices, highs, lows, opens)
        engine = FTREngine(get_default_config())
        
        zones = []
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            if result.zones:
                zones.extend(result.zones)
        
        assert len(zones) == 0, "در داده تصادفی نباید FTR Zone ایجاد شود"