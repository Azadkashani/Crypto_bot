# FILE: scripts/analyze_trades.py

"""
اسکریپت تحلیل کیفیت معاملات Backtest
"""

import sys
import os
import json

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
from src.strategy.signal.signal_quality_types import SignalQualityConfig


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
                min_impulse_candles=2, max_impulse_candles=25,
                min_impulse_distance_pct=0.0005, min_body_ratio=0.3,
                max_retracement_during_impulse=0.25,
            ),
            base_config=BaseDetectorConfig(
                min_base_candles=2, max_base_candles=30,
                max_retracement_pct=0.75, max_base_range_pct=0.40,
            ),
            zone_config=ZoneConstructorConfig(
                invalidation_buffer_pct=0.10, min_zone_height_pct=0.0003,
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=50, min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.9, allow_wick_touch=True, allow_close_touch=True,
            )
        )
    )


def main():
    loader = HistoricalDataLoader()
    universe = ["BTC_USDT", "ETH_USDT", "XRP_USDT", "BNB_USDT",
                "SOL_USDT", "LINK_USDT", "UNI_USDT", "DOGE_USDT",
                "ADA_USDT", "HYPE_USDT", "ZEC_USDT", "SUI_USDT"]
    
    signal_quality_config = SignalQualityConfig(
        min_qualified_score=65.0,
        min_watch_score=45.0,
    )
    
    all_trades = []
    
    for symbol in universe:
        csv_path = f"data/historical/{symbol}_1h.csv"
        
        if not os.path.exists(csv_path):
            continue
        
        candles, info, validation = loader.load_csv(csv_path, symbol=symbol, timeframe="1h")
        
        if not validation.is_valid:
            continue
        
        pipeline_config = build_pipeline_config(symbol, "1h", 1000.0)
        pipeline = StrategyPipeline(pipeline_config)
        pipeline.signal_quality_engine.config = signal_quality_config
        
        for i in range(2, len(candles)):
            visible = candles[:i+1]
            result = pipeline.process_candle(visible, i)
            
            for signal in result.signals:
                if signal.status == "COMPLETE" and signal.trade_signal:
                    ts = signal.trade_signal
                    zone = signal.signal_quality.metadata.get('zone_id', 'unknown')
                    
                    entry = ts.entry_price
                    sl = ts.stop_loss
                    tp = ts.take_profit
                    direction = ts.direction
                    rr = ts.risk_reward
                    
                    # جستجوی خروج از معامله
                    exit_price = None
                    exit_reason = None
                    
                    # ایندکس سیگنال
                    signal_index = i
                    
                    for j in range(signal_index + 1, min(signal_index + 100, len(candles))):
                        c = candles[j]
                        
                        if direction == "LONG":
                            if c['low'] <= sl:
                                exit_price = sl
                                exit_reason = "STOP_LOSS"
                                break
                            if c['high'] >= tp:
                                exit_price = tp
                                exit_reason = "TAKE_PROFIT"
                                break
                        else:
                            if c['high'] >= sl:
                                exit_price = sl
                                exit_reason = "STOP_LOSS"
                                break
                            if c['low'] <= tp:
                                exit_price = tp
                                exit_reason = "TAKE_PROFIT"
                                break
                    
                    if exit_price is not None:
                        if direction == "LONG":
                            pnl = (exit_price - entry) / entry * 100
                        else:
                            pnl = (entry - exit_price) / entry * 100
                    else:
                        exit_reason = "TIMEOUT"
                        exit_price = candles[min(signal_index + 99, len(candles)-1)]['close']
                        if direction == "LONG":
                            pnl = (exit_price - entry) / entry * 100
                        else:
                            pnl = (entry - exit_price) / entry * 100
                    
                    all_trades.append({
                        'symbol': symbol,
                        'direction': direction,
                        'signal_index': signal_index,
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'rr_planned': rr,
                        'exit': exit_price,
                        'exit_reason': exit_reason,
                        'pnl_pct': pnl,
                        'zone_id': zone,
                    })
    
    # گزارش
    print("=" * 70)
    print("TRADE QUALITY ANALYSIS")
    print("=" * 70)
    
    for i, trade in enumerate(all_trades):
        print(f"\nTrade #{i+1}")
        print(f"  Symbol:    {trade['symbol']}")
        print(f"  Direction: {trade['direction']}")
        print(f"  Index:     {trade['signal_index']}")
        print(f"  Entry:     {trade['entry']:.6f}")
        print(f"  SL:        {trade['sl']:.6f}")
        print(f"  TP:        {trade['tp']:.6f}")
        print(f"  R:R Plan:  1:{trade['rr_planned']:.2f}")
        print(f"  Exit:      {trade['exit']:.6f}")
        print(f"  Reason:    {trade['exit_reason']}")
        print(f"  PnL:       {trade['pnl_pct']:.4f}%")
        
        if trade['pnl_pct'] > 0:
            print(f"  Result:    ✅ WIN")
        elif trade['pnl_pct'] < 0:
            print(f"  Result:    ❌ LOSS")
        else:
            print(f"  Result:    ➖ BREAKEVEN")
    
    # خلاصه
    if all_trades:
        wins = sum(1 for t in all_trades if t['pnl_pct'] > 0)
        losses = sum(1 for t in all_trades if t['pnl_pct'] < 0)
        be = sum(1 for t in all_trades if t['pnl_pct'] == 0)
        avg_pnl = sum(t['pnl_pct'] for t in all_trades) / len(all_trades)
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Trades: {len(all_trades)}")
        print(f"Wins:  {wins}")
        print(f"Losses: {losses}")
        print(f"Breakeven: {be}")
        print(f"Win Rate: {wins}/{len(all_trades)} = {wins/len(all_trades)*100:.1f}%")
        print(f"Average PnL: {avg_pnl:.4f}%")
        
        # تفکیک
        sl_trades = [t for t in all_trades if t['exit_reason'] == 'STOP_LOSS']
        tp_trades = [t for t in all_trades if t['exit_reason'] == 'TAKE_PROFIT']
        
        print(f"\nTP Hits: {len(tp_trades)}")
        print(f"SL Hits: {len(sl_trades)}")
        print(f"TP Rate: {len(tp_trades)}/{len(all_trades)} = {len(tp_trades)/len(all_trades)*100:.1f}%")
    
    # ذخیره
    with open("data/historical/trade_quality_report.json", "w") as f:
        json.dump(all_trades, f, indent=2)
    
    print(f"\nReport: data/historical/trade_quality_report.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
