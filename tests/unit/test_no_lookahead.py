# FILE: tests/unit/test_no_lookahead.py

"""
تست‌های عدم وجود Look-ahead Bias
"""

import pytest
from typing import List
from src.strategy.ftr.ftr_engine import FTREngine
from tests.unit.test_ftr_detection import (
    create_bullish_ftr_scenario, get_default_config
)


class TestNoLookahead:
    """تست‌های جلوگیری از Look-ahead Bias"""
    
    def test_causal_detection(self):
        """
        تست اینکه تشخیص FTR فقط از داده‌های گذشته استفاده می‌کند
        """
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        # پردازش تا کندل 30
        for i in range(2, 30):
            engine.process_bar(ohlcv_data, i)
        
        zones_at_30 = engine.get_all_zones()
        
        # بازنشانی و پردازش تا کندل 50
        engine.reset()
        for i in range(2, 50):
            engine.process_bar(ohlcv_data, i)
        
        zones_at_50 = engine.get_all_zones()
        
        # Zoneهای تشخیص داده شده در کندل 30 نباید تحت تأثیر داده‌های بعدی باشند
        # یعنی Zoneهایی که تا 30 تشخیص شده‌اند باید زیرمجموعه Zoneهای تا 50 باشند
        zone_ids_at_30 = {z.zone_id for z in zones_at_30}
        zone_ids_at_50 = {z.zone_id for z in zones_at_50}
        
        assert zone_ids_at_30.issubset(zone_ids_at_50), \
            "Zoneهای تشخیص داده شده نباید با داده‌های آینده تغییر کنند"
    
    def test_no_future_swing_usage(self):
        """
        تست عدم استفاده از Swingهای آینده
        """
        from src.strategy.market_structure.swing_detector import SwingDetector
        
        ohlcv_data = create_bullish_ftr_scenario()
        detector = SwingDetector()
        
        # پردازش تا کندل 20
        confirmed_at_20 = []
        for i in range(2, 20):
            new_swings = detector.process_bar(ohlcv_data, i)
            confirmed_at_20.extend(new_swings)
        
        # Swingهای تأیید شده در کندل 20
        # نباید شامل Swingهایی باشند که نیاز به داده بعد از 20 دارند
        for swing in confirmed_at_20:
            assert swing.index + detector.config.pivot_right <= 19, \
                f"Swing در ایندکس {swing.index} نیاز به داده آینده دارد"
    
    def test_zone_creation_time(self):
        """
        تست زمان ایجاد Zone
        """
        ohlcv_data = create_bullish_ftr_scenario()
        engine = FTREngine(get_default_config())
        
        for i in range(2, len(ohlcv_data)):
            result = engine.process_bar(ohlcv_data, i)
            
            if result.zones:
                for zone in result.zones:
                    # Zone باید در زمان فعلی یا قبل ایجاد شده باشد
                    assert zone.created_timestamp <= ohlcv_data[i]['timestamp'], \
                        "Zone نباید با داده آینده ایجاد شده باشد"
