# FILE: scripts/validate_impulse_params.py

"""
اسکریپت تحلیل کنترل‌شده پارامترهای ImpulseDetector
بدون تغییر Production Code
"""

import sys
import os
import json
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.ftr.ftr_engine import FTREngine, FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig


UNIVERSE = [
    "BTC_USDT", "ETH_USDT", "XRP_USDT", "BNB_USDT",
    "SOL_USDT", "LINK_USDT", "UNI_USDT", "DOGE_USDT",
    "ADA_USDT", "HYPE_USDT", "ZEC_USDT", "SUI_USDT"
]


CONFIGS = {
    "A": {
        "min_impulse_candles": 2,
        "max_impulse_candles": 10,
        "min_impulse_distance_pct": 0.003,
        "min_body_ratio": 0.5,
        "max_retracement_during_impulse": 0.25,
    },
    "B": {
        "min_impulse_candles": 2,
        "max_impulse_candles": 15,
        "min_impulse_distance_pct": 0.002,
        "min_body_ratio": 0.5,
        "max_retracement_during_impulse": 0.25,
    },
    "C": {
        "min_impulse_candles": 2,
        "max_impulse_candles": 20,
        "min_impulse_distance_pct": 0.001,
        "min_body_ratio": 0.5,
        "max_retracement_during_impulse": 0.25,
    },
    "D": {
        "min_impulse_candles": 2,
        "max_impulse_candles": 20,
        "min_impulse_distance_pct": 0.001,
        "min_body_ratio": 0.3,
        "max_retracement_during_impulse": 0.25,
    },
}


def build_ftr_config(symbol: str, timeframe: str, impulse_params: Dict) -> FTREngineConfig:
    """ساخت FTR Config با پارامترهای Impulse مشخص"""
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
        impulse_config=ImpulseDetectorConfig(**impulse_params),
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


def analyze_symbol(symbol: str, candles: List[Dict], config_name: str, impulse_params: Dict) -> Dict:
    """تحلیل یک نماد با پارامترهای مشخص"""
    engine = FTREngine(build_ftr_config(symbol, "1h", impulse_params))
    
    total_breaks = 0
    valid_impulses = 0
    invalid_impulses = 0
    zones = 0
    ftb_events = 0
    
    for i in range(2, len(candles)):
        visible = candles[:i+1]
        result = engine.process_bar(visible, i)
    
    # شمارش نهایی
    total_breaks = len(engine.structure_analyzer.get_recent_breaks())
    zones = len(engine.get_all_zones())
    ftb_events = len(engine.get_ftb_events())
    
    # بررسی Impulse برای هر Break
    breaks = engine.structure_analyzer.get_recent_breaks()
    
    for sb in breaks:
        # یافتن break_index
        break_index = None
        for j, c in enumerate(candles):
            if c['timestamp'] == sb.break_timestamp:
                break_index = j
                break
        
        if break_index is not None:
            displacement = engine.impulse_detector.detect_impulse(
                candles[:break_index + 1 + impulse_params.get('max_impulse_candles', 10)],
                break_index,
                sb.direction
            )
            
            # تحلیل دستی
            if break_index + 1 < len(candles):
                start_price = candles[break_index]['close']
                max_close = start_price
                impulse_count = 0
                
                end_idx = min(break_index + 1 + impulse_params.get('max_impulse_candles', 10), len(candles))
                
                for k in range(break_index + 1, end_idx):
                    c = candles[k]
                    if sb.direction == "LONG":
                        if c['close'] > max_close:
                            max_close = c['close']
                            impulse_count += 1
                    else:
                        if c['close'] < max_close:
                            max_close = c['close']
                            impulse_count += 1
                
                if sb.direction == "LONG":
                    distance = (max_close - start_price) / start_price
                else:
                    distance = (start_price - max_close) / start_price
                
                min_distance = impulse_params.get('min_impulse_distance_pct', 0.003)
                
                if impulse_count >= impulse_params.get('min_impulse_candles', 2) and distance >= min_distance:
                    valid_impulses += 1
                else:
                    invalid_impulses += 1
    
    return {
        'symbol': symbol,
        'breaks': total_breaks,
        'valid_impulses': valid_impulses,
        'invalid_impulses': invalid_impulses,
        'zones': zones,
        'ftb_events': ftb_events,
    }


def main():
    loader = HistoricalDataLoader()
    
    results = {}
    
    for config_name, params in CONFIGS.items():
        print(f"\n{'='*50}")
        print(f"CONFIG {config_name}: {params}")
        print(f"{'='*50}")
        
        config_results = []
        
        for symbol in UNIVERSE:
            csv_path = f"data/historical/{symbol}_1h.csv"
            
            if not os.path.exists(csv_path):
                print(f"  {symbol}: MISSING")
                continue
            
            candles, info, validation = loader.load_csv(csv_path, symbol=symbol, timeframe="1h")
            
            if not validation.is_valid:
                print(f"  {symbol}: INVALID")
                continue
            
            result = analyze_symbol(symbol, candles, config_name, params)
            config_results.append(result)
            
            print(f"  {symbol}: breaks={result['breaks']}, "
                  f"impulse_valid={result['valid_impulses']}, "
                  f"impulse_invalid={result['invalid_impulses']}, "
                  f"zones={result['zones']}, ftb={result['ftb_events']}")
        
        # جمع‌بندی
        total_breaks = sum(r['breaks'] for r in config_results)
        total_valid = sum(r['valid_impulses'] for r in config_results)
        total_invalid = sum(r['invalid_impulses'] for r in config_results)
        total_zones = sum(r['zones'] for r in config_results)
        
        print(f"\n  TOTAL: breaks={total_breaks}, valid_impulses={total_valid}, "
              f"invalid={total_invalid}, zones={total_zones}")
        
        results[config_name] = {
            'params': params,
            'per_symbol': config_results,
            'totals': {
                'breaks': total_breaks,
                'valid_impulses': total_valid,
                'invalid_impulses': total_invalid,
                'zones': total_zones,
            }
        }
    
    # ذخیره گزارش
    report_path = "data/historical/impulse_validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nReport saved: {report_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
