# FILE: scripts/diagnose_ftr.py

"""
اسکریپت تشخیصی برای بررسی FTR Pipeline
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
                min_impulse_candles=2, max_impulse_candles=10,
                min_impulse_distance_pct=0.003, min_body_ratio=0.5
            ),
            base_config=BaseDetectorConfig(
                min_base_candles=3, max_base_candles=20,
                max_retracement_pct=0.382, max_base_range_pct=0.30
            ),
            zone_config=ZoneConstructorConfig(
                invalidation_buffer_pct=0.10, min_zone_height_pct=0.0005
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=50, min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.8, allow_wick_touch=True, allow_close_touch=True
            )
        )
    )


def main():
    symbol = "BTC_USDT"
    timeframe = "1h"
    
    loader = HistoricalDataLoader()
    candles, info, validation = loader.load_csv(
        f"data/historical/{symbol}_{timeframe}.csv",
        symbol=symbol, timeframe=timeframe
    )
    
    print(f"Candles: {len(candles)}")
    
    pipeline_config = build_pipeline_config(symbol, timeframe, 1000.0)
    pipeline = StrategyPipeline(pipeline_config)
    
    # آمار
    swing_count = 0
    structure_levels_count = 0
    breaks_count = 0
    impulse_count = 0
    base_count = 0
    zone_count = 0
    ftb_count = 0
    
    for i in range(2, min(200, len(candles))):
        visible = candles[:i+1]
        result = pipeline.process_candle(visible, i)
        
        # دسترسی به اجزای FTR Engine
        ftr_engine = pipeline.ftr_engine
        
        swing_count = len(ftr_engine.structure_analyzer._all_swings)
        structure_levels_count = len(ftr_engine.structure_analyzer._structure_levels)
        breaks_count = len(ftr_engine.structure_analyzer._recent_breaks)
        zone_count = len(ftr_engine.get_all_zones())
        ftb_count = len(ftr_engine.get_ftb_events())
        
        if i % 25 == 0:
            print(f"i={i}: swings={swing_count}, levels={structure_levels_count}, "
                  f"breaks={breaks_count}, zones={zone_count}, ftb={ftb_count}")
    
    print(f"\nFINAL: swings={swing_count}, levels={structure_levels_count}, "
          f"breaks={breaks_count}, zones={zone_count}, ftb={ftb_count}")


if __name__ == '__main__':
    main()
