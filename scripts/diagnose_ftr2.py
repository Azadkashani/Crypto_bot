# FILE: scripts/diagnose_ftr2.py

"""
اسکریپت تشخیصی دقیق‌تر — بررسی Impulse و Base بعد از Break
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.ftr.ftr_engine import FTREngine, FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


def build_ftr_config(symbol, timeframe):
    return FTREngineConfig(
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


def main():
    symbol = "BTC_USDT"
    timeframe = "1h"
    
    loader = HistoricalDataLoader()
    candles, info, validation = loader.load_csv(
        f"data/historical/{symbol}_{timeframe}.csv",
        symbol=symbol, timeframe=timeframe
    )
    
    print(f"Candles: {len(candles)}")
    
    engine = FTREngine(build_ftr_config(symbol, timeframe))
    
    for i in range(2, min(200, len(candles))):
        visible = candles[:i+1]
        result = engine.process_bar(visible, i)
        
        breaks = engine.structure_analyzer.get_recent_breaks()
        
        if breaks:
            # بررسی هر Break
            for idx, sb in enumerate(breaks):
                break_index = None
                for j, c in enumerate(visible):
                    if c['timestamp'] == sb.break_timestamp:
                        break_index = j
                        break
                
                if break_index is not None and break_index < len(visible) - 3:
                    # تلاش برای Impulse
                    displacement = engine.impulse_detector.detect_impulse(
                        visible, break_index, sb.direction
                    )
                    
                    impulse_status = "VALID" if displacement and displacement.is_valid else "INVALID/NONE"
                    
                    if displacement and displacement.is_valid:
                        base = engine.base_detector.detect_base(visible, displacement)
                        base_status = "VALID" if base and base.is_valid else "INVALID/NONE"
                        
                        if base and base.is_valid:
                            zone = engine.zone_constructor.construct_zone(
                                symbol=symbol, timeframe=timeframe,
                                direction=sb.direction,
                                structure_level=sb.broken_level,
                                structure_break=sb,
                                displacement=displacement,
                                base=base,
                                current_timestamp=visible[i]['timestamp']
                            )
                            
                            if zone:
                                zone_status = "CREATED" if engine.zone_constructor.validate_zone(zone) else "INVALID"
                                print(f"i={i}: Break#{idx} dir={sb.direction} "
                                      f"impulse={impulse_status} base={base_status} zone={zone_status}")
                            else:
                                print(f"i={i}: Break#{idx} dir={sb.direction} "
                                      f"impulse={impulse_status} base={base_status} zone=None")
                        else:
                            print(f"i={i}: Break#{idx} dir={sb.direction} "
                                  f"impulse={impulse_status} base={base_status}")
                    else:
                        if i > break_index + 5:
                            print(f"i={i}: Break#{idx} dir={sb.direction} "
                                  f"impulse={impulse_status} (break_index={break_index})")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
