# FILE: scripts/diagnose_signal_quality.py

"""
اسکریپت تشخیصی Signal Quality — چرا امتیاز پایین است
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.pipeline.strategy_pipeline import StrategyPipeline, StrategyPipelineConfig
from src.strategy.ftr.ftr_engine import FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def build_pipeline_config(symbol, timeframe, initial_equity):
    return StrategyPipelineConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_equity=initial_equity,
        ftr_config=FTREngineConfig(
            symbol=symbol,
            timeframe=timeframe,
            swing_config=SwingDetectorConfig(
                pivot_left=3, pivot_right=3, min_swing_distance_pct=0.001
            ),
            structure_config=StructureAnalyzerConfig(
                min_level_strength=2, level_tolerance_pct=0.001,
                break_validation_candles=1, min_break_distance_pct=0.001
            ),
            impulse_config=ImpulseDetectorConfig(
                min_impulse_candles=2, max_impulse_candles=20,
                min_impulse_distance_pct=0.001, min_body_ratio=0.5,
                max_retracement_during_impulse=0.25,
            ),
            base_config=BaseDetectorConfig(
                min_base_candles=3, max_base_candles=20,
                max_retracement_pct=0.60, max_base_range_pct=0.30,
            ),
            zone_config=ZoneConstructorConfig(
                invalidation_buffer_pct=0.10, min_zone_height_pct=0.0005,
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=50, min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.8, allow_wick_touch=True, allow_close_touch=True,
            )
        )
    )


def main():
    symbol = "UNI_USDT"
    timeframe = "1h"
    
    loader = HistoricalDataLoader()
    candles, info, validation = loader.load_csv(
        f"data/historical/{symbol}_{timeframe}.csv",
        symbol=symbol, timeframe=timeframe
    )
    
    pipeline_config = build_pipeline_config(symbol, timeframe, 1000.0)
    pipeline = StrategyPipeline(pipeline_config)
    
    print(f"Symbol: {symbol}, Candles: {len(candles)}")
    print()
    
    signal_count = 0
    
    for i in range(2, len(candles)):
        visible = candles[:i+1]
        result = pipeline.process_candle(visible, i)
        
        for signal in result.signals:
            signal_count += 1
            
            sq = signal.signal_quality
            
            if sq is not None:
                print(f"{'='*60}")
                print(f"Signal #{signal_count} at index {i}")
                print(f"Status: {signal.status}")
                print(f"Direction: {sq.direction}")
                print(f"Score: {sq.score:.2f}")
                print(f"Classification: {sq.classification.value}")
                print(f"-" * 50)
                print(f"  Structure:    {sq.component_scores.structure_score:.1f}/20")
                print(f"  Displacement: {sq.component_scores.displacement_score:.1f}/20")
                print(f"  Base:         {sq.component_scores.base_score:.1f}/15")
                print(f"  Zone:         {sq.component_scores.zone_score:.1f}/15")
                print(f"  FTB:          {sq.component_scores.ftb_score:.1f}/20")
                print(f"  Trend:        {sq.component_scores.trend_score:.1f}/10")
                print(f"-" * 50)
                print(f"Positive factors:")
                for f in sq.positive_factors:
                    print(f"  + {f}")
                print(f"Warning factors:")
                for f in sq.warning_factors:
                    print(f"  ! {f}")
                print(f"{'='*60}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
