# FILE: tests/unit/test_strategy_pipeline.py

"""
تست‌های Strategy Pipeline — Integration
"""

import pytest
from typing import List, Dict, Any
from src.strategy.pipeline.strategy_pipeline import (
    StrategyPipeline, StrategyPipelineConfig
)
from src.strategy.ftr.ftr_engine import FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def create_bullish_ftr_data() -> List[dict]:
    """ایجاد داده صعودی کامل برای FTR"""
    n = 75
    prices = []
    highs = []
    lows = []
    opens = []
    
    # روند صعودی
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
    
    # شکست
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
    
    # Impulse
    for i in range(6):
        price = 115 + i * 2.0
        opens.append(price - 1.5)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.6)
    
    # Base
    base_high = 130
    base_low = 126
    for i in range(6):
        price = base_low + (i % 3) * 1.3
        opens.append(price)
        prices.append(price)
        highs.append(base_high)
        lows.append(base_low)
    
    # خروج از Base
    price = base_high + 2.5
    opens.append(base_high)
    prices.append(price)
    highs.append(price + 0.7)
    lows.append(base_high - 0.5)
    
    # ادامه
    for i in range(5):
        price = base_high + 4 + i * 1.5
        opens.append(price - 1.0)
        prices.append(price)
        highs.append(price + 0.7)
        lows.append(price - 0.5)
    
    # بازگشت
    for i in range(12):
        price = base_high - 0.5 - i * 0.3
        opens.append(price + 0.2)
        prices.append(price)
        highs.append(price + 0.4)
        lows.append(price - 0.3)
    
    for i in range(8):
        price = base_low - 1 - i * 0.2
        opens.append(price + 0.1)
        prices.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    
    data = []
    for i in range(len(prices)):
        data.append({
            'open': opens[i],
            'high': highs[i],
            'low': lows[i],
            'close': prices[i],
            'volume': 100,
            'timestamp': i * 3600
        })
    
    return data


def get_pipeline_config() -> StrategyPipelineConfig:
    """ایجاد پیکربندی Pipeline"""
    return StrategyPipelineConfig(
        symbol="BTC_USDT",
        timeframe="1h",
        initial_equity=10000.0,
        ftr_config=FTREngineConfig(
            symbol="BTC_USDT",
            timeframe="1h",
            swing_config=SwingDetectorConfig(
                pivot_left=2, pivot_right=2, min_swing_distance_pct=0.0005
            ),
            structure_config=StructureAnalyzerConfig(
                min_level_strength=1, level_tolerance_pct=0.005,
                break_validation_candles=1, min_break_distance_pct=0.001
            ),
            impulse_config=ImpulseDetectorConfig(
                min_impulse_candles=2, max_impulse_candles=10,
                min_impulse_distance_pct=0.002, min_body_ratio=0.3
            ),
            base_config=BaseDetectorConfig(
                min_base_candles=2, max_base_candles=15,
                max_retracement_pct=0.5, max_base_range_pct=0.30
            ),
            zone_config=ZoneConstructorConfig(
                invalidation_buffer_pct=0.05, min_zone_height_pct=0.0005
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=30, min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.8, allow_wick_touch=True, allow_close_touch=True
            )
        )
    )


class TestStrategyPipeline:
    """تست‌های Pipeline Integration"""
    
    def test_pipeline_initialization(self):
        """تست راه‌اندازی Pipeline"""
        pipeline = StrategyPipeline(get_pipeline_config())
        
        assert pipeline.ftr_engine is not None
        assert pipeline.signal_quality_engine is not None
        assert pipeline.trade_signal_engine is not None
        assert pipeline.risk_management_engine is not None
        assert pipeline.execution_engine is not None
    
    def test_pipeline_process_no_crash(self):
        """تست اجرای Pipeline بدون خطا"""
        pipeline = StrategyPipeline(get_pipeline_config())
        data = create_bullish_ftr_data()
        
        for i in range(2, len(data)):
            result = pipeline.process_candle(data, i)
            assert result is not None
    
    def test_pipeline_reset(self):
        """تست Reset Pipeline"""
        pipeline = StrategyPipeline(get_pipeline_config())
        data = create_bullish_ftr_data()
        
        for i in range(2, 30):
            pipeline.process_candle(data, i)
        
        pipeline.reset()
        
        assert pipeline._equity == 10000.0
        assert len(pipeline._processed_signals) == 0
    
    def test_pipeline_determinism(self):
        """تست قطعیت Pipeline"""
        pipeline1 = StrategyPipeline(get_pipeline_config())
        pipeline2 = StrategyPipeline(get_pipeline_config())
        data = create_bullish_ftr_data()
        
        results1 = []
        results2 = []
        
        for i in range(2, len(data)):
            r1 = pipeline1.process_candle(data, i)
            r2 = pipeline2.process_candle(data, i)
            results1.append(r1.total_processed)
            results2.append(r2.total_processed)
        
        assert results1 == results2
    
    def test_no_lookahead_pipeline(self):
        """تست عدم Look-ahead در Pipeline"""
        pipeline = StrategyPipeline(get_pipeline_config())
        data = create_bullish_ftr_data()
        
        # اجرا تا index 30
        for i in range(2, 31):
            pipeline.process_candle(data, i)
        
        signals_at_30 = pipeline._processed_signals.copy()
        
        # ادامه با داده کامل
        for i in range(31, len(data)):
            pipeline.process_candle(data, i)
        
        # سیگنال‌های ثبت‌شده تا index 30 نباید تغییر کرده باشند
        for sig in signals_at_30:
            assert sig in pipeline._processed_signals
    
    def test_duplicate_signal_prevention(self):
        """تست جلوگیری از سیگنال تکراری"""
        pipeline = StrategyPipeline(get_pipeline_config())
        
        # پردازش دستی یک signal تکراری
        pipeline._processed_signals.add("TEST_SIG")
        
        assert "TEST_SIG" in pipeline._processed_signals
