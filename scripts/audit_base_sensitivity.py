# FILE: scripts/audit_base_sensitivity.py

"""
اسکریپت تحلیل حساسیت Base Detection — بدون تغییر Production Code
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
from src.strategy.types.ftr_types import DisplacementData


UNIVERSE = [
    "BTC_USDT", "ETH_USDT", "XRP_USDT", "BNB_USDT",
    "SOL_USDT", "LINK_USDT", "UNI_USDT", "DOGE_USDT",
    "ADA_USDT", "HYPE_USDT", "ZEC_USDT", "SUI_USDT"
]


CONFIGS = {
    "A": {
        "name": "Baseline",
        "base_params": {
            "min_base_candles": 3,
            "max_base_candles": 20,
            "max_retracement_pct": 0.382,
            "max_base_range_pct": 0.30,
        },
        "strong_exit_body_ratio": 0.5,
    },
    "B": {
        "name": "Relax Retracement",
        "base_params": {
            "min_base_candles": 3,
            "max_base_candles": 20,
            "max_retracement_pct": 0.50,
            "max_base_range_pct": 0.30,
        },
        "strong_exit_body_ratio": 0.5,
    },
    "C": {
        "name": "More Relaxed Retracement",
        "base_params": {
            "min_base_candles": 3,
            "max_base_candles": 20,
            "max_retracement_pct": 0.60,
            "max_base_range_pct": 0.30,
        },
        "strong_exit_body_ratio": 0.5,
    },
    "D": {
        "name": "Relax Retracement + Exit Candle",
        "base_params": {
            "min_base_candles": 3,
            "max_base_candles": 20,
            "max_retracement_pct": 0.50,
            "max_base_range_pct": 0.30,
        },
        "strong_exit_body_ratio": 0.30,
    },
}


def build_ftr_config(symbol: str, base_params: Dict, strong_exit_body_ratio: float) -> FTREngineConfig:
    """ساخت FTR Config با پارامترهای Base مشخص"""
    return FTREngineConfig(
        symbol=symbol,
        timeframe="1h",
        swing_config=SwingDetectorConfig(
            pivot_left=3, pivot_right=3, min_swing_distance_pct=0.001
        ),
        structure_config=StructureAnalyzerConfig(
            min_level_strength=2, level_tolerance_pct=0.001,
            break_validation_candles=1, min_break_distance_pct=0.001
        ),
        impulse_config=ImpulseDetectorConfig(
            min_impulse_candles=2,
            max_impulse_candles=20,
            min_impulse_distance_pct=0.001,
            min_body_ratio=0.5,
            max_retracement_during_impulse=0.25,
        ),
        base_config=BaseDetectorConfig(**base_params),
        zone_config=ZoneConstructorConfig(
            invalidation_buffer_pct=0.10,
            min_zone_height_pct=0.0005,
        ),
        ftb_config=FTBDetectorConfig(
            max_ftb_wait_candles=50,
            min_touch_depth_pct=0.0,
            max_touch_depth_pct=0.8,
            allow_wick_touch=True,
            allow_close_touch=True,
        )
    )


def manual_analyze(symbol, candles, base_params, strong_exit_body_ratio):
    """تحلیل دستی Base Detection"""
    engine = FTREngine(build_ftr_config(symbol, base_params, strong_exit_body_ratio))
    
    stats = {
        'breaks': 0,
        'valid_impulses': 0,
        'base_candidates': 0,
        'valid_bases': 0,
        'reasons': {},
    }
    
    # اجرای Pipeline
    for i in range(2, len(candles)):
        visible = candles[:i+1]
        engine.process_bar(visible, i)
    
    stats['breaks'] = len(engine.structure_analyzer.get_recent_breaks())
    stats['zones'] = len(engine.get_all_zones())
    stats['ftb'] = len(engine.get_ftb_events())
    
    breaks = engine.structure_analyzer.get_recent_breaks()
    
    for sb in breaks:
        break_index = None
        for j, c in enumerate(candles):
            if c['timestamp'] == sb.break_timestamp:
                break_index = j
                break
        
        if break_index is None:
            continue
        
        # Impulse دستی
        start_price = candles[break_index]['close']
        current_extreme = start_price
        impulse_candles = []
        max_distance = 0.0
        end_index = break_index
        
        for k in range(break_index + 1, min(break_index + 1 + 20, len(candles))):
            c = candles[k]
            
            if sb.direction == "LONG":
                if c['close'] > current_extreme:
                    current_extreme = c['close']
                    end_index = k
                    max_distance = current_extreme - start_price
                    impulse_candles.append(k)
                else:
                    if max_distance > 0:
                        ret = (current_extreme - c['close']) / max_distance
                        if ret > 0.25:
                            break
            else:
                if c['close'] < current_extreme:
                    current_extreme = c['close']
                    end_index = k
                    max_distance = start_price - current_extreme
                    impulse_candles.append(k)
                else:
                    if max_distance > 0:
                        ret = (c['close'] - current_extreme) / max_distance
                        if ret > 0.25:
                            break
        
        if len(impulse_candles) < 2 or max_distance <= 0:
            continue
        
        distance_pct = max_distance / start_price
        
        if distance_pct < 0.001:
            continue
        
        stats['valid_impulses'] += 1
        
        # Base Detection دستی
        displacement = DisplacementData(
            start_price=start_price,
            end_price=current_extreme,
            start_timestamp=candles[break_index]['timestamp'],
            end_timestamp=candles[end_index]['timestamp'],
            direction=sb.direction,
            candle_count=len(impulse_candles),
            strength_score=0.5,
            avg_candle_range=0.0,
            start_index=break_index,
            end_index=end_index,
        )
        
        # بررسی Base
        start_check = end_index + 1
        base_candles = []
        base_high = float('-inf')
        base_low = float('inf')
        base_found = False
        
        max_base_candles = base_params.get('max_base_candles', 20)
        max_retracement = base_params.get('max_retracement_pct', 0.382)
        
        for k in range(start_check, min(start_check + max_base_candles, len(candles))):
            c = candles[k]
            
            base_high = max(base_high, c['high'])
            base_low = min(base_low, c['low'])
            
            # بررسی retracement
            if sb.direction == "LONG":
                retracement = (displacement.end_price - c['low']) / displacement.distance
            else:
                retracement = (c['high'] - displacement.end_price) / displacement.distance
            
            if retracement > max_retracement:
                stats['reasons']['RETRACEMENT_EXCEEDED'] = stats['reasons'].get('RETRACEMENT_EXCEEDED', 0) + 1
                break
            
            base_candles.append(k)
            
            # بررسی کامل بودن Base
            if len(base_candles) >= base_params.get('min_base_candles', 3):
                last_c = candles[k]
                body = abs(last_c['close'] - last_c['open'])
                range_val = last_c['high'] - last_c['low']
                
                is_bullish_exit = last_c['close'] > last_c['open'] if sb.direction == "LONG" else last_c['close'] < last_c['open']
                
                if range_val > 0 and body / range_val > strong_exit_body_ratio and is_bullish_exit:
                    base_found = True
                    break
        
        stats['base_candidates'] += 1
        
        if base_found:
            stats['valid_bases'] += 1
        else:
            # تعیین دلیل
            if len(base_candles) >= base_params.get('min_base_candles', 3):
                stats['reasons']['NO_STRONG_EXIT'] = stats['reasons'].get('NO_STRONG_EXIT', 0) + 1
            else:
                stats['reasons']['INSUFFICIENT_BASE_CANDLES'] = stats['reasons'].get('INSUFFICIENT_BASE_CANDLES', 0) + 1
    
    return stats


def main():
    loader = HistoricalDataLoader()
    
    all_results = {}
    
    for config_name, config in CONFIGS.items():
        print(f"\n{'='*60}")
        print(f"CONFIG {config_name}: {config['name']}")
        print(f"  Base params: {config['base_params']}")
        print(f"  Strong exit body ratio: {config['strong_exit_body_ratio']}")
        print(f"{'='*60}")
        
        total = {
            'breaks': 0, 'valid_impulses': 0, 'base_candidates': 0,
            'valid_bases': 0, 'zones': 0, 'ftb': 0,
            'reasons': {},
        }
        
        per_symbol = {}
        
        for symbol in UNIVERSE:
            csv_path = f"data/historical/{symbol}_1h.csv"
            
            if not os.path.exists(csv_path):
                continue
            
            candles, info, validation = loader.load_csv(csv_path, symbol=symbol, timeframe="1h")
            
            if not validation.is_valid:
                continue
            
            stats = manual_analyze(
                symbol, candles, config['base_params'], config['strong_exit_body_ratio']
            )
            
            per_symbol[symbol] = stats
            
            for key in ['breaks', 'valid_impulses', 'base_candidates', 'valid_bases', 'zones', 'ftb']:
                total[key] += stats[key]
            
            for reason, count in stats['reasons'].items():
                total['reasons'][reason] = total['reasons'].get(reason, 0) + count
            
            print(f"  {symbol:<12}: breaks={stats['breaks']:>4}, imp={stats['valid_impulses']:>4}, "
                  f"base_cand={stats['base_candidates']:>4}, base_ok={stats['valid_bases']:>3}, "
                  f"zones={stats['zones']:>3}, ftb={stats['ftb']:>3}")
        
        print(f"\n  TOTAL: breaks={total['breaks']}, imp={total['valid_impulses']}, "
              f"base_cand={total['base_candidates']}, base_ok={total['valid_bases']}, "
              f"zones={total['zones']}, ftb={total['ftb']}")
        
        print(f"  Reasons:")
        for reason, count in sorted(total['reasons'].items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")
        
        all_results[config_name] = {
            'config': config,
            'per_symbol': per_symbol,
            'totals': total,
        }
    
    with open("data/historical/base_sensitivity_report.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\nReport saved: data/historical/base_sensitivity_report.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
