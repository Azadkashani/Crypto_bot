# FILE: scripts/audit_base_detection.py

"""
اسکریپت تحلیل Base Detection — چرا Valid Impulse به Zone تبدیل نمی‌شود
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


def build_ftr_config(symbol: str, timeframe: str) -> FTREngineConfig:
    """ساخت FTR Config با Config C"""
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
            min_impulse_candles=2,
            max_impulse_candles=20,
            min_impulse_distance_pct=0.001,
            min_body_ratio=0.5,
            max_retracement_during_impulse=0.25,
        ),
        base_config=BaseDetectorConfig(
            min_base_candles=3,
            max_base_candles=20,
            max_retracement_pct=0.382,
            max_base_range_pct=0.30,
        ),
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


def analyze_base_detection(symbol: str, candles: List[Dict]) -> Dict:
    """تحلیل کامل Base Detection برای یک نماد"""
    engine = FTREngine(build_ftr_config(symbol, "1h"))
    
    # آمار
    stats = {
        'breaks': 0,
        'valid_impulses': 0,
        'base_candidates': 0,
        'valid_bases': 0,
        'zone_candidates': 0,
        'zones': 0,
        'rejection_reasons': {},
    }
    
    # اجرای Pipeline برای همه کندل‌ها
    for i in range(2, len(candles)):
        visible = candles[:i+1]
        engine.process_bar(visible, i)
    
    stats['breaks'] = len(engine.structure_analyzer.get_recent_breaks())
    stats['zones'] = len(engine.get_all_zones())
    
    # تحلیل دستی Impulse → Base
    breaks = engine.structure_analyzer.get_recent_breaks()
    
    for sb in breaks:
        # یافتن break_index
        break_index = None
        for j, c in enumerate(candles):
            if c['timestamp'] == sb.break_timestamp:
                break_index = j
                break
        
        if break_index is None:
            continue
        
        # ساخت Impulse به صورت دستی
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
                        retracement = (current_extreme - c['close']) / max_distance
                        if retracement > 0.25:
                            break
            else:  # SHORT
                if c['close'] < current_extreme:
                    current_extreme = c['close']
                    end_index = k
                    max_distance = start_price - current_extreme
                    impulse_candles.append(k)
                else:
                    if max_distance > 0:
                        retracement = (c['close'] - current_extreme) / max_distance
                        if retracement > 0.25:
                            break
        
        # بررسی Valid Impulse
        if len(impulse_candles) < 2:
            continue
        
        if max_distance <= 0:
            continue
        
        distance_pct = max_distance / start_price
        
        if distance_pct < 0.001:
            continue
        
        stats['valid_impulses'] += 1
        
        # ساخت DisplacementData
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
        
        # تلاش برای Base Detection
        base = engine.base_detector.detect_base(
            candles[:min(end_index + 20, len(candles))],
            displacement
        )
        
        if base is not None and base.is_valid:
            stats['valid_bases'] += 1
            
            # تلاش برای Zone
            zone = engine.zone_constructor.construct_zone(
                symbol=symbol,
                timeframe="1h",
                direction=sb.direction,
                structure_level=sb.broken_level,
                structure_break=sb,
                displacement=displacement,
                base=base,
                current_timestamp=candles[end_index]['timestamp'],
            )
            
            if zone is not None and engine.zone_constructor.validate_zone(zone):
                stats['zone_candidates'] += 1
            else:
                reason = "ZONE_INVALID"
                stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
        else:
            # تعیین دلیل رد Base
            if base is None:
                reason = "BASE_NOT_FOUND"
            else:
                reason = "BASE_INVALID"
            
            stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
    
    return stats


def main():
    loader = HistoricalDataLoader()
    
    all_symbol_stats = {}
    total_stats = {
        'breaks': 0,
        'valid_impulses': 0,
        'base_candidates': 0,
        'valid_bases': 0,
        'zone_candidates': 0,
        'zones': 0,
        'rejection_reasons': {},
    }
    
    print(f"{'Symbol':<12} | {'Breaks':>6} | {'Impulse':>8} | {'Base OK':>7} | {'Zone OK':>7} | {'FTR':>5}")
    print("-" * 65)
    
    for symbol in UNIVERSE:
        csv_path = f"data/historical/{symbol}_1h.csv"
        
        if not os.path.exists(csv_path):
            print(f"{symbol:<12} | MISSING")
            continue
        
        candles, info, validation = loader.load_csv(csv_path, symbol=symbol, timeframe="1h")
        
        if not validation.is_valid:
            print(f"{symbol:<12} | INVALID")
            continue
        
        stats = analyze_base_detection(symbol, candles)
        all_symbol_stats[symbol] = stats
        
        # به‌روزرسانی کل
        for key in ['breaks', 'valid_impulses', 'valid_bases', 'zone_candidates', 'zones']:
            total_stats[key] += stats[key]
        
        for reason, count in stats['rejection_reasons'].items():
            total_stats['rejection_reasons'][reason] = total_stats['rejection_reasons'].get(reason, 0) + count
        
        print(f"{symbol:<12} | {stats['breaks']:>6} | {stats['valid_impulses']:>8} | "
              f"{stats['valid_bases']:>7} | {stats['zone_candidates']:>7} | {stats['zones']:>5}")
    
    print("-" * 65)
    print(f"{'TOTAL':<12} | {total_stats['breaks']:>6} | {total_stats['valid_impulses']:>8} | "
          f"{total_stats['valid_bases']:>7} | {total_stats['zone_candidates']:>7} | {total_stats['zones']:>5}")
    
    print(f"\nRejection Reasons:")
    for reason, count in sorted(total_stats['rejection_reasons'].items(), key=lambda x: -x[1]):
        pct = count / total_stats['valid_impulses'] * 100 if total_stats['valid_impulses'] > 0 else 0
        print(f"  {reason}: {count} ({pct:.1f}%)")
    
    # ذخیره گزارش
    report = {
        'totals': total_stats,
        'per_symbol': all_symbol_stats,
    }
    
    with open("data/historical/base_detection_audit.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport: data/historical/base_detection_audit.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
