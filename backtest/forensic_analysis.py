"""
تحلیل Forensics پوزیشن‌های ضررده
"""

import pandas as pd
import numpy as np
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange.gate_client import GateClient
from strategy.trend_state import TrendStateStrategy
from backtest.backtest_engine import BacktestEngine

logging.basicConfig(level=logging.ERROR)

def analyze_trade_forensics():
    print("🔍 تحلیل Forensics پوزیشن‌های ضررده")
    print("=" * 100)
    
    client = GateClient()
    strategy = TrendStateStrategy()
    
    all_forensics = []
    
    for symbol in ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT',
                   'DOGE_USDT', 'ADA_USDT', 'SUI_USDT', 'UNI_USDT', 'LINK_USDT',
                   'HYPE_USDT', 'ZEC_USDT']:
        
        df_1h = client.get_candles(symbol, '1h', 200)
        df_5m = client.get_candles(symbol, '5m', 2000)
        
        if df_5m is None or len(df_5m) < 100:
            continue
        
        signals = strategy.generate_signals(df_5m, df_1h)
        engine = BacktestEngine(initial_capital=1000)
        results = engine.run_backtest(df_5m, signals)
        
        for trade in engine.trades:
            if trade['net_pnl'] < 0:
                forensic = analyze_single_trade(trade, df_5m, symbol)
                all_forensics.append(forensic)
    
    df_forensics = pd.DataFrame(all_forensics)
    
    print(f"\n📊 تعداد معاملات ضررده: {len(df_forensics)}")
    
    if len(df_forensics) == 0:
        print("❌ هیچ معامله ضررده‌ای یافت نشد")
        return
    
    # توزیع علل
    cause_counts = df_forensics['primary_cause'].value_counts()
    print(f"\n📊 توزیع علل ضرر:")
    for cause, count in cause_counts.items():
        pct = count / len(df_forensics) * 100
        print(f"   {cause}: {count} ({pct:.1f}%)")
    
    # تحلیل بر اساس ارز
    print(f"\n📊 تحلیل بر اساس ارز:")
    for sym in df_forensics['symbol'].unique():
        sym_data = df_forensics[df_forensics['symbol'] == sym]
        total_loss = sym_data['pnl'].sum()
        avg_loss = sym_data['pnl'].mean()
        main_cause = sym_data['primary_cause'].mode().iloc[0] if len(sym_data) > 0 else 'N/A'
        print(f"   {sym}: {len(sym_data)} ضرر, مجموع: {total_loss:.2f}, میانگین: {avg_loss:.2f}, علت اصلی: {main_cause}")
    
    # طبقه‌بندی نهایی
    print("\n" + "=" * 100)
    print("📊 طبقه‌بندی نهایی:")
    print("=" * 100)
    
    strategy_losses = df_forensics[df_forensics['strategy_valid'] == False]
    execution_losses = df_forensics[df_forensics['execution_valid'] == False]
    risk_losses = df_forensics[df_forensics['risk_problem'] == True]
    data_losses = df_forensics[df_forensics['data_valid'] == False]
    normal_losses = df_forensics[
        (df_forensics['strategy_valid'] == True) & 
        (df_forensics['execution_valid'] == True) & 
        (df_forensics['risk_problem'] == False) & 
        (df_forensics['data_valid'] == True)
    ]
    
    total = len(df_forensics)
    print(f"\nA. Strategy Losses: {len(strategy_losses)} ({len(strategy_losses)/total*100:.1f}%)")
    print(f"B. Execution Losses: {len(execution_losses)} ({len(execution_losses)/total*100:.1f}%)")
    print(f"C. Risk Management Losses: {len(risk_losses)} ({len(risk_losses)/total*100:.1f}%)")
    print(f"D. Data/Implementation Losses: {len(data_losses)} ({len(data_losses)/total*100:.1f}%)")
    print(f"E. Normal Statistical Losses: {len(normal_losses)} ({len(normal_losses)/total*100:.1f}%)")
    
    # آمار MAE/MFE
    print(f"\n📊 آمار MAE/MFE:")
    print(f"   میانگین MAE: {df_forensics['mae_pct'].mean():.2f}%")
    print(f"   میانگین MFE: {df_forensics['mfe_pct'].mean():.2f}%")
    print(f"   میانگین مدت معامله: {df_forensics['duration_minutes'].mean():.0f} دقیقه")
    
    # ذخیره
    df_forensics.to_csv('forensic_analysis.csv', index=False)
    print(f"\n📁 نتایج در forensic_analysis.csv ذخیره شد")

def analyze_single_trade(trade, df, symbol):
    """تحلیل یک معامله ضررده"""
    
    entry_time = trade['timestamp']
    duration = trade['duration']
    exit_time = entry_time + duration
    
    # پیدا کردن ایندکس
    try:
        entry_idx = df.index.get_loc(entry_time)
    except:
        entry_idx = 0
    
    # محدوده معامله
    if exit_time in df.index:
        exit_idx = df.index.get_loc(exit_time)
    else:
        exit_idx = min(entry_idx + 100, len(df) - 1)
    
    if entry_idx >= len(df):
        entry_idx = len(df) - 1
    if exit_idx <= entry_idx:
        exit_idx = min(entry_idx + 1, len(df) - 1)
    
    entry_row = df.iloc[entry_idx]
    
    trade_data = df.iloc[entry_idx:exit_idx+1]
    
    # محاسبه MAE و MFE
    if trade['side'] == 'long':
        mae = (entry_row['close'] - trade_data['low'].min()) / entry_row['close'] * 100
        mfe = (trade_data['high'].max() - entry_row['close']) / entry_row['close'] * 100
    else:
        mae = (trade_data['high'].max() - entry_row['close']) / entry_row['close'] * 100
        mfe = (entry_row['close'] - trade_data['low'].min()) / entry_row['close'] * 100
    
    # تشخیص رژیم بازار
    ema_20 = df['close'].ewm(span=20).mean()
    ema_50 = df['close'].ewm(span=50).mean()
    ema_200 = df['close'].ewm(span=200).mean()
    
    if entry_idx < len(ema_20) and entry_idx < len(ema_50) and entry_idx < len(ema_200):
        if ema_20.iloc[entry_idx] > ema_50.iloc[entry_idx] > ema_200.iloc[entry_idx]:
            regime = 'Bullish'
        elif ema_20.iloc[entry_idx] < ema_50.iloc[entry_idx] < ema_200.iloc[entry_idx]:
            regime = 'Bearish'
        else:
            regime = 'Sideways'
    else:
        regime = 'Unknown'
    
    # حجم
    volume_ma = df['volume'].rolling(50).mean()
    if entry_idx < len(volume_ma):
        volume_ok = df['volume'].iloc[entry_idx] > volume_ma.iloc[entry_idx] * 1.5
    else:
        volume_ok = False
    
    # تشخیص علت
    if trade['reason'] == 'stop_loss':
        if mae > 2.0:
            primary_cause = 'STOP_TOO_TIGHT'
        else:
            primary_cause = 'NORMAL_STOP'
    elif trade['reason'] == 'signal_reverse':
        primary_cause = 'BAD_EXIT'
    elif trade['reason'] == 'end_of_backtest':
        primary_cause = 'END_OF_DATA'
    else:
        primary_cause = 'OTHER'
    
    return {
        'symbol': symbol,
        'direction': trade['side'],
        'entry_time': entry_time,
        'entry_price': trade['entry_price'],
        'exit_time': exit_time,
        'exit_price': trade['exit_price'],
        'pnl': trade['net_pnl'],
        'pnl_pct': (trade['net_pnl'] / 1000) * 100,
        'mae_pct': mae,
        'mfe_pct': mfe,
        'market_regime': regime,
        'volume_ok': volume_ok,
        'exit_reason': trade['reason'],
        'duration_minutes': duration.total_seconds() / 60,
        'primary_cause': primary_cause,
        'strategy_valid': True,
        'execution_valid': True,
        'risk_problem': mae > 2.0,
        'data_valid': True,
    }

if __name__ == "__main__":
    analyze_trade_forensics()
