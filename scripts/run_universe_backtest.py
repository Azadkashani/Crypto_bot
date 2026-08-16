# FILE: scripts/run_universe_backtest.py

"""
اسکریپت اجرای Backtest روی هر ۱۲ نماد
+ حذف سیگنال تکراری
+ حد سود = ۴ برابر حد ضرر
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.config.trading_universe import TradingUniverseConfig
from src.strategy.pipeline.strategy_pipeline import StrategyPipeline, StrategyPipelineConfig
from src.strategy.ftr.ftr_engine import FTREngineConfig
from src.strategy.market_structure.swing_detector import SwingDetectorConfig
from src.strategy.market_structure.structure_analyzer import StructureAnalyzerConfig
from src.strategy.ftr.impulse_detector import ImpulseDetectorConfig
from src.strategy.ftr.base_detector import BaseDetectorConfig
from src.strategy.ftr.zone_constructor import ZoneConstructorConfig
from src.strategy.ftr.ftb_detector import FTBDetectorConfig
from src.strategy.signal.signal_quality_types import SignalQualityConfig

TARGET_RR = 4.0  # حد سود = ۴ برابر حد ضرر


def build_pipeline_config(symbol: str, timeframe: str, initial_equity: float) -> StrategyPipelineConfig:
    """ساخت پیکربندی کامل Pipeline"""
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
                invalidation_buffer_pct=0.25,  # افزایش از 0.10 به 0.25
                min_zone_height_pct=0.0003,
            ),
            ftb_config=FTBDetectorConfig(
                max_ftb_wait_candles=50, min_touch_depth_pct=0.0,
                max_touch_depth_pct=0.9, allow_wick_touch=True, allow_close_touch=True,
            )
        )
    )


def calculate_tp_fixed_rr(entry: float, sl: float, direction: str, target_rr: float = TARGET_RR) -> float:
    """محاسبه TP با R:R ثابت"""
    risk = abs(entry - sl)
    
    if direction == "LONG":
        return entry + (risk * target_rr)
    else:
        return entry - (risk * target_rr)


def main():
    parser = argparse.ArgumentParser(description='Run Multi-Symbol FTR Backtest')
    parser.add_argument('--timeframe', default='1h', help='Timeframe')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--initial-equity', type=float, default=1000.0, help='Initial equity')
    
    args = parser.parse_args()
    
    loader = HistoricalDataLoader()
    universe = TradingUniverseConfig()
    
    signal_quality_config = SignalQualityConfig(
        min_qualified_score=65.0,
        min_watch_score=45.0,
    )
    
    print("=" * 50)
    print("FTR MULTI-SYMBOL BACKTEST")
    print("=" * 50)
    print(f"Universe: {universe.get_symbol_count()} symbols")
    print(f"Timeframe: {args.timeframe}")
    print(f"Initial Equity: ${args.initial_equity}")
    print(f"Risk/Trade: {universe.risk_per_trade * 100}%")
    print(f"Position Allocation: {universe.position_equity_fraction * 100}%")
    print(f"Max Positions: {universe.max_open_positions}")
    print(f"Max per Symbol: {universe.max_position_per_symbol}")
    print(f"Min Volume: {universe.min_futures_volume_usdt:,.0f} USDT")
    print(f"Margin: {universe.margin_mode.value.upper()}")
    print(f"Target R:R: 1:{TARGET_RR}")
    print("=" * 50)
    
    datasets = {}
    
    for symbol in universe.symbols:
        csv_path = os.path.join(args.data_dir, f"{symbol}_{args.timeframe}.csv")
        
        if os.path.exists(csv_path):
            candles, info, validation = loader.load_csv(
                csv_path, symbol=symbol, timeframe=args.timeframe
            )
            if validation.is_valid:
                datasets[symbol] = candles
                print(f"  {symbol}: READY ({info.row_count} candles)")
            else:
                print(f"  {symbol}: INVALID")
        else:
            print(f"  {symbol}: MISSING")
    
    if not datasets:
        print("\nNo data available.")
        return 1
    
    print("\nBACKTEST RUNNING...\n")
    
    total_stats = {
        'ftr_zones': 0, 'ftb_events': 0, 'qualified': 0, 'watch': 0,
        'rejected': 0, 'trade_signals': 0, 'risk_accepted': 0,
        'orders': 0, 'trades': 0, 'duplicates': 0,
    }
    
    per_symbol_stats = {}
    processed_signal_keys: Set[str] = set()  # جلوگیری از Duplicate
    executed_trades: Set[str] = set()  # جلوگیری از اجرای تکراری
    
    # ذخیره Trade ها برای تحلیل
    all_trades = []
    
    for symbol, candles in datasets.items():
        pipeline_config = build_pipeline_config(symbol, args.timeframe, args.initial_equity)
        pipeline = StrategyPipeline(pipeline_config)
        pipeline.signal_quality_engine.config = signal_quality_config
        
        symbol_stats = {
            'ftr_zones': 0, 'ftb_events': 0, 'qualified': 0, 'watch': 0,
            'rejected': 0, 'trade_signals': 0, 'risk_accepted': 0,
            'orders': 0, 'trades': 0, 'duplicates': 0,
        }
        
        for current_index in range(2, len(candles)):
            visible_ohlcv = candles[:current_index + 1]
            
            result = pipeline.process_candle(visible_ohlcv, current_index)
            
            symbol_stats['ftr_zones'] = len(pipeline.ftr_engine.get_all_zones())
            symbol_stats['ftb_events'] = len(pipeline.ftr_engine.get_ftb_events())
            
            for signal in result.signals:
                # Duplicate Check: بر اساس signal_id
                signal_key = signal.signal_id
                
                if signal_key in processed_signal_keys:
                    symbol_stats['duplicates'] += 1
                    continue
                
                processed_signal_keys.add(signal_key)
                
                if signal.status != "COMPLETE":
                    if signal.status == "WATCH":
                        symbol_stats['watch'] += 1
                    elif signal.status in ["REJECTED", "RISK_REJECTED", "EXECUTION_REJECTED"]:
                        symbol_stats['rejected'] += 1
                    continue
                
                symbol_stats['qualified'] += 1
                
                trade_signal = signal.trade_signal
                if trade_signal is None:
                    continue
                
                # اعمال TP = 4 × SL
                entry = trade_signal.entry_price
                sl = trade_signal.stop_loss
                direction = trade_signal.direction
                
                new_tp = calculate_tp_fixed_rr(entry, sl, direction, TARGET_RR)
                trade_signal.take_profit = new_tp
                trade_signal.risk_reward = TARGET_RR
                
                # جلوگیری از اجرای تکراری
                trade_key = f"{symbol}_{direction}_{entry}_{sl}_{new_tp}"
                
                if trade_key in executed_trades:
                    symbol_stats['duplicates'] += 1
                    continue
                
                executed_trades.add(trade_key)
                
                symbol_stats['trade_signals'] += 1
                
                if signal.risk_assessment and signal.risk_assessment.is_valid:
                    symbol_stats['risk_accepted'] += 1
                    
                    if signal.execution_result and signal.execution_result.success:
                        symbol_stats['orders'] += 1
                        symbol_stats['trades'] += 1
                        
                        # ثبت Trade برای تحلیل
                        all_trades.append({
                            'symbol': symbol,
                            'direction': direction,
                            'signal_index': current_index,
                            'entry': entry,
                            'sl': sl,
                            'tp': new_tp,
                            'rr': TARGET_RR,
                        })
        
        for key in total_stats:
            total_stats[key] += symbol_stats[key]
        
        per_symbol_stats[symbol] = symbol_stats
        
        print(f"  {symbol}: {symbol_stats['ftr_zones']} FTR, "
              f"{symbol_stats['ftb_events']} FTB, "
              f"{symbol_stats['qualified']} QUALIFIED, "
              f"{symbol_stats['watch']} WATCH, "
              f"{symbol_stats['rejected']} REJECTED, "
              f"{symbol_stats['duplicates']} DUP, "
              f"{symbol_stats['trades']} trades")
    
    # شبیه‌سازی خروج از معاملات
    print("\n" + "=" * 50)
    print("TRADE SIMULATION")
    print("=" * 50)
    
    wins = 0
    losses = 0
    total_pnl_pct = 0.0
    
    for trade in all_trades:
        symbol = trade['symbol']
        entry = trade['entry']
        sl = trade['sl']
        tp = trade['tp']
        direction = trade['direction']
        idx = trade['signal_index']
        
        candles = datasets[symbol]
        
        exit_price = None
        exit_reason = None
        
        for j in range(idx + 1, min(idx + 100, len(candles))):
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
        
        if exit_price is None:
            exit_reason = "TIMEOUT"
            exit_price = candles[min(idx + 99, len(candles)-1)]['close']
        
        if direction == "LONG":
            pnl_pct = (exit_price - entry) / entry * 100
        else:
            pnl_pct = (entry - exit_price) / entry * 100
        
        if pnl_pct > 0:
            wins += 1
        else:
            losses += 1
        
        total_pnl_pct += pnl_pct
        
        print(f"  {symbol} {direction}: entry={entry:.6f}, sl={sl:.6f}, "
              f"tp={tp:.6f}, exit={exit_price:.6f}, reason={exit_reason}, "
              f"pnl={pnl_pct:.4f}%")
    
    avg_pnl = total_pnl_pct / len(all_trades) if all_trades else 0
    
    print()
    print("=" * 50)
    print("BACKTEST RESULT")
    print("=" * 50)
    print(f"Initial Equity: ${args.initial_equity}")
    print(f"Total Trades:   {total_stats['trades']}")
    print(f"Duplicates:     {total_stats['duplicates']}")
    print(f"Wins:  {wins}")
    print(f"Losses: {losses}")
    print(f"Win Rate: {wins}/{len(all_trades)} = {wins/len(all_trades)*100:.1f}%" if all_trades else "N/A")
    print(f"Average PnL:   {avg_pnl:.4f}%")
    print("-" * 50)
    print(f"FTR Zones:      {total_stats['ftr_zones']}")
    print(f"FTB Events:     {total_stats['ftb_events']}")
    print(f"QUALIFIED:      {total_stats['qualified']}")
    print(f"WATCH:          {total_stats['watch']}")
    print(f"REJECTED:       {total_stats['rejected']}")
    print(f"Trade Signals:  {total_stats['trade_signals']}")
    print("=" * 50)
    
    report_path = os.path.join(args.data_dir, "universe_backtest_report.json")
    report = {
        'config': {
            'target_rr': TARGET_RR,
            'min_qualified_score': 65,
        },
        'total_stats': total_stats,
        'per_symbol': per_symbol_stats,
        'trades': all_trades,
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport: {report_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
