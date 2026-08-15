# FILE: tests/unit/test_ftb_detection.py

"""
تست‌های تشخیص First Time Back
"""

import pytest
from typing import List
from src.strategy.types.ftr_types import FTRZone, FTRZoneState, FTBEvent, FTBTouchType
from src.strategy.ftr.ftb_detector import FTBDetector, FTBDetectorConfig


class TestFTBDetection:
    """تست‌های FTB"""
    
    def create_test_zone(self, direction="LONG") -> FTRZone:
        """ایجاد Zone تستی"""
        if direction == "LONG":
            zone = FTRZone(
                zone_id="test_long",
                symbol="BTC_USDT",
                timeframe="1h",
                direction="LONG",
                zone_high=105.0,
                zone_low=100.0,
                zone_midpoint=102.5,
                created_timestamp=0,
                invalidation_level=98.0,
                state=FTRZoneState.ACTIVE
            )
        else:
            zone = FTRZone(
                zone_id="test_short",
                symbol="BTC_USDT",
                timeframe="1h",
                direction="SHORT",
                zone_high=105.0,
                zone_low=100.0,
                zone_midpoint=102.5,
                created_timestamp=0,
                invalidation_level=107.0,
                state=FTRZoneState.ACTIVE
            )
        
        return zone
    
    def test_first_touch_detection_long(self):
        """تست تشخیص اولین لمس برای LONG"""
        zone = self.create_test_zone("LONG")
        detector = FTBDetector(FTBDetectorConfig(
            allow_wick_touch=True,
            allow_close_touch=True,
            min_touch_depth_pct=0.0,
            max_touch_depth_pct=0.8
        ))
        
        detector.add_zone(zone)
        
        # کندل که وارد Zone می‌شود
        ohlcv_data = [
            {'open': 110, 'high': 111, 'low': 104, 'close': 104.5, 'volume': 100, 'timestamp': 3600},
            {'open': 104, 'high': 105, 'low': 101, 'close': 102, 'volume': 100, 'timestamp': 7200}
        ]
        
        # پردازش کندل دوم
        ftb = detector.check_ftb(ohlcv_data, 1, zone)
        
        assert ftb is not None, "FTB باید تشخیص داده شود"
        assert ftb.is_valid, "FTB باید معتبر باشد"
        assert zone.touch_count == 1, "باید یک لمس ثبت شود"
        assert zone.first_touch_timestamp == 7200, "زمان اولین لمس ثبت شود"
        assert zone.state == FTRZoneState.FIRST_TOUCH, "وضعیت Zone باید FIRST_TOUCH شود"
    
    def test_second_touch_not_first(self):
        """تست اینکه لمس دوم به عنوان FTB شناخته نشود"""
        zone = self.create_test_zone("LONG")
        detector = FTBDetector(FTBDetectorConfig())
        
        detector.add_zone(zone)
        
        # ثبت لمس اول
        zone.register_touch(104.0, 3600, FTBTouchType.WICK)
        zone.update_state(FTRZoneState.FIRST_TOUCH)
        
        # کندل دوم که دوباره وارد Zone می‌شود
        ohlcv_data = [
            {'open': 104, 'high': 105, 'low': 102, 'close': 103, 'volume': 100, 'timestamp': 7200}
        ]
        
        # Zone باید مصرف شده باشد
        zone.consume(3600)
        
        # بررسی FTB
        ftb = detector.check_ftb(ohlcv_data, 0, zone)
        
        assert ftb is None, "لمس دوم نباید به عنوان FTB شناخته شود"
    
    def test_zone_invalidation(self):
        """تست ابطال Zone"""
        zone = self.create_test_zone("LONG")
        detector = FTBDetector(FTBDetectorConfig())
        
        detector.add_zone(zone)
        
        # کندل که Zone را ابطال می‌کند
        ohlcv_data = [
            {'open': 99, 'high': 99.5, 'low': 97, 'close': 97.5, 'volume': 100, 'timestamp': 3600}
        ]
        
        # بررسی ابطال
        if ohlcv_data[0]['close'] < zone.invalidation_level:
            zone.invalidate(3600)
        
        assert zone.state == FTRZoneState.INVALIDATED, "Zone باید ابطال شود"
        
        # FTB نباید برای Zone ابطال شده تشخیص داده شود
        ohlcv_data_ftb = [
            {'open': 104, 'high': 105, 'low': 102, 'close': 103, 'volume': 100, 'timestamp': 7200}
        ]
        
        ftb = detector.check_ftb(ohlcv_data_ftb, 0, zone)
        assert ftb is None, "FTB برای Zone ابطال شده نباید تشخیص داده شود"
    
    def test_penetration_too_deep(self):
        """تست نفوذ بیش از حد عمیق"""
        zone = self.create_test_zone("LONG")
        detector = FTBDetector(FTBDetectorConfig(
            min_touch_depth_pct=0.0,
            max_touch_depth_pct=0.5  # حداکثر 50% نفوذ
        ))
        
        detector.add_zone(zone)
        
        # کندل که بیش از 50% Zone نفوذ می‌کند
        ohlcv_data = [
            {'open': 104, 'high': 105, 'low': 99, 'close': 99.5, 'volume': 100, 'timestamp': 3600}
        ]
        
        ftb = detector.check_ftb(ohlcv_data, 0, zone)
        
        # نفوذ از 105 تا 99.5 = 5.5 واحد، ارتفاع Zone = 5 واحد
        # نفوذ = 5.5/5 = 110% که بیش از 50% است
        assert ftb is None or not ftb.is_valid, "نفوذ بیش از حد نباید FTB معتبر ایجاد کند"
