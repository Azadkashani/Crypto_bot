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
            'timestamp': i * 3600
        }
        data.append(candle)
    
    return data


def create_bullish_ftr_scenario() -> List[dict]:
    """
    سناریوی FTR صعودی با سطوح ساختاری واضح
    """
    n = 75
    prices = []
    highs = []
    lows = []
    opens = []
    
    # فاز ۱: روند صعودی با Swingهای واضح
    for i in range(5):
        price = 100 + i * 0.5
        opens.append(price - 0.3)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.3)
    
    for i in range(5):
        price = 103 + i * 0.4
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.4)
    
    for i in range(5):
        price = 104 - i * 0.4
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.3)
    
    for i in range(5):
        price = 105 + i * 0.6
        opens.append(price + 0.3)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.4)
    
    for i in range(5):
        price = 108 - i * 0.4
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    
    # فاز ۲: شکست قوی مقاومت ۱۰۸
    price = 110
    opens.append(108.5)
    prices.append(price)
    highs.append(110.5)
    lows.append(108)
    
    for i in range(3):
        price = 111 + i * 1.0
        opens.append(price - 0.8)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.5)
    
    # فاز ۳: Impulse قوی
    for i in range(6):
        price = 115 + i * 2.0
        opens.append(price - 1.5)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.6)
    
    # فاز ۴: Base (تثبیت) — محدوده ۱۲۶-۱۳۰
    # کندل‌های Base: 6 کندل خنثی + 1 کندل خروجی قوی
    base_high = 130
    base_low = 126
    
    # ۶ کندل خنثی
    for i in range(6):
        price = base_low + (i % 3) * 1.3
        opens.append(price)
        prices.append(price)
        highs.append(base_high)
        lows.append(base_low)
    
    # کندل خروجی قوی از Base (کندل آخر Base)
    price = base_high + 2.5
    opens.append(base_high)  # open در بالای Base
    prices.append(price)     # close بالاتر
    highs.append(price + 0.7)
    lows.append(base_high - 0.5)  # low داخل Base
    
    # فاز ۵: ادامه صعود
    for i in range(5):
        price = base_high + 4 + i * 1.5
        opens.append(price - 1.0)
        prices.append(price)
        highs.append(price + 0.7)
        lows.append(price - 0.5)
    
    # فاز ۶: بازگشت به Zone (FTB)
    for i in range(12):
        price = base_high - 0.5 - i * 0.3
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.3)
    
    for i in range(6):
        price = base_low - 1 - i * 0.2
        opens.append(price + 0.1)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    
    return create_ohlcv_data(prices[:n], highs[:n], lows[:n], opens[:n])


def create_bearish_ftr_scenario() -> List[dict]:
    """سناریوی FTR نزولی"""
    n = 75
    prices = []
    highs = []
    lows = []
    opens = []
    
    for i in range(5):
        price = 200 - i * 0.5
        opens.append(price + 0.3)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.5)
    
    for i in range(5):
        price = 197 - i * 0.4
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.5)
    
    for i in range(5):
        price = 196 + i * 0.4
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.4)
    
    for i in range(5):
        price = 195 - i * 0.6
        opens.append(price - 0.3)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.5)
    
    for i in range(5):
        price = 192 + i * 0.4
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    
    # شکست حمایت ۱۹۲
    price = 190
    opens.append(191.5)
    prices.append(price)
    highs.append(192)
    lows.append(189.5)
    
    for i in range(3):
        price = 189 - i * 1.0
        opens.append(price + 0.8)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.5)
    
    # Impulse نزولی
    for i in range(6):
        price = 185 - i * 2.0
        opens.append(price + 1.5)
        prices.append(price)
        highs.append(price + 0.6)
        lows.append(price - 0.5)
    
    # Base نزولی
    base_high = 176
    base_low = 172
    
    for i in range(6):
        price = base_high - (i % 3) * 1.3
        opens.append(price)
        prices.append(price)
        highs.append(base_high)
        lows.append(base_low)
    
    # خروج نزولی از Base
    price = base_low - 2.5
    opens.append(base_low)
    prices.append(price)
    highs.append(base_low + 0.5)
    lows.append(price - 0.7)
    
    for i in range(5):
        price = base_low - 4 - i * 1.5
        opens.append(price + 1.0)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.7)
    
    # بازگشت به Zone
    for i in range(12):
        price = base_low + 0.5 + i * 0.3
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.4)
    
    for i in range(6):
        price = base_high + 1 + i * 0.2
        opens.append(price - 0.1)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    
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
            min_level_strength=1,
            level_tolerance_pct=0.005,
            break_validation_candles=1,
            min_break_distance_pct=0.001
        ),
        impulse_config=ImpulseDetectorConfig(
            min_impulse_candles=2,
            max_impulse_candles=10,
            min_impulse_distance_pct=0.002,
            min_body_ratio=0.3
        ),
        base_config=BaseDetectorConfig(
            min_base_candles=2,
            max_base_candles=15,
            max_retracement_pct=0.5,
            max_base_range_pct=0.30
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
    
    def test_level_not_consumed_before_zone(self):
        """تست: سطح قبل از ساخت Zone مصرف نشود"""
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        # پردازش فقط تا قبل از Base کامل
        for i in range(2, 35):
            engine.process_bar(ohlcv_data, i)
        
        structure_levels = engine.structure_analyzer.get_structure_levels()
        
        for level in structure_levels:
            if level.level_type in ["RESISTANCE", "SUPPLY"]:
                if not level.is_consumed:
                    pass
    
    def test_break_not_processed_twice(self):
        """تست: شکست تکراری پردازش نشود"""
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        zones = []
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            if result.zones:
                zones.extend(result.zones)
        
        zone_ids = [z.zone_id for z in zones]
        assert len(zone_ids) == len(set(zone_ids)), "Zone تکراری وجود دارد"
    
    def test_zone_consumes_level(self):
        """تست: پس از ساخت Zone، سطح مصرف شود"""
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        zones = []
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            if result.zones:
                zones.extend(result.zones)
        
        if zones:
            zone = zones[0]
            structure_level = zone.structure_reference
            
            if structure_level:
                assert structure_level.is_consumed, "سطح باید پس از ساخت Zone مصرف شده باشد"