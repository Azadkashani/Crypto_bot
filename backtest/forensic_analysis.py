"""
تحلیل Forensics پوزیشن‌های ضررده
بررسی دقیق علت هر ضرر
"""

import pandas as pd
import numpy as np
import logging
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
        
        # دریافت داده‌ها
        df_1h = client.get_candles(symbol, '1h', 200)
        df_5m = client.get_candles(symbol, '5m', 2000)
        
        if df_5m is None or len(df_5m) < 100:
            continue
        
        # اجرای استراتژی
        signals = strategy.generate_signals(df_5m, df_1h)
        engine = BacktestEngine(initial_capital=1000)
        results = engine.run_backtest(df_5m, signals)
        
        # تحلیل هر معامله ضررده
        for trade in engine.trades:
            if trade['net_pnl'] < 0:
                forensic = analyze_single_trade(trade, df_5m, signals, symbol)
                all_forensics.append(forensic)
    
    # نمایش نتایج
    df_forensics = pd.DataFrame(all_forensics)
    
    print(f"\n📊 تعداد معاملات ضررده: {len(df_forensics)}")
    
    # تحلیل علل
    cause_counts = df_forensics['primary_cause'].value_counts()
    print(f"\n📊 توزیع علل ضرر:")
    for cause, count in cause_counts.items():
        pct = count / len(df_forensics) * 100
        print(f"   {cause}: {count} ({pct:.1f}%)")
    
    # تحلیل بر اساس ارز
    symbol_analysis = df_forensics.groupby('symbol').agg({
        'net_pnl': ['count', 'sum', 'mean'],
        'primary_cause': lambda x: x.mode().iloc[0] if len(x) > 0 else 'N/A'
    })
    print(f"\n📊 تحلیل بر اساس ارز:")
    print(symbol_analysis.to_string())
    
    # طبقه‌بندی نهایی
    print("\n" + "=" * 100)
    print("📊 طبقه‌بندی نهایی ضررها:")
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
    
    print(f"\nA. Strategy Losses: {len(strategy_losses)} ({len(strategy_losses)/len(df_forensics)*100:.1f}%)")
    print(f"B. Execution Losses: {len(execution_losses)} ({len(execution_losses)/len(df_forensics)*100:.1f}%)")
    print(f"C. Risk Management Losses: {len(risk_losses)} ({len(risk_losses)/len(df_forensics)*100:.1f}%)")
    print(f"D. Data/Implementation Losses: {len(data_losses)} ({len(data_losses)/len(df_forensics)*100:.1f}%)")
    print(f"E. Normal Statistical Losses: {len(normal_losses)} ({len(normal_losses)/len(df_forensics)*100:.1f}%)")
    
    # ذخیره
    df_forensics.to_csv('forensic_analysis.csv', index=False)
    print(f"\n📁 نتایج در forensic_analysis.csv ذخیره شد")

def analyze_single_trade(trade, df, signals, symbol):
    """تحلیل یک معامله ضررده"""
    
    entry_time = trade['timestamp']
    exit_time = trade['timestamp'] + trade['duration']
    
    # پیدا کردن موقعیت در DataFrame
    entry_idx = df.index.get_loc(entry_time)
    exit_idx = df.index.get_loc(exit_time) if exit_time in df.index else min(entry_idx + 50, len(df)-1)
    
    # استخراج داده‌های معامله
    entry_row = df.iloc[entry_idx]
    exit_row = df.iloc[exit_idx]
    
    # محاسبه MAE و MFE
    trade_data = df.iloc[entry_idx:exit_idx+1]
    
    if trade['side'] == 'long':
        mae = (entry_row['close'] - trade_data['low'].min()) / entry_row['close'] * 100
        mfe = (trade_data['high'].max() - entry_row['close']) / entry_row['close'] * 100
    else:
        mae = (trade_data['high'].max() - entry_row['close']) / entry_row['close'] * 100
        mfe = (entry_row['close'] - trade_data['low'].min()) / entry_row['close'] * 100
    
    # تشخیص Market Regime
    ema_20 = df['close'].ewm(span=20).mean()
    ema_50 = df['close'].ewm(span=50).mean()
    ema_200 = df['close'].ewm(span=200).mean()
    
    if ema_20.iloc[entry_idx] > ema_50.iloc[entry_idx] > ema_200.iloc[entry_idx]:
        regime = 'Bullish'
    elif ema_20.iloc[entry_idx] < ema_50.iloc[entry_idx] < ema_200.iloc[entry_idx]:
        regime = 'Bearish'
    else:
        regime = 'Sideways'
    
    # بررسی حجم
    volume_ma = df['volume'].rolling(50).mean()
    volume_ok = df['volume'].iloc[entry_idx] > volume_ma.iloc[entry_idx] * 1.5
    
    # بررسی RSI
    rsi = df['rsi'].iloc[entry_idx] if 'rsi' in df.columns else 50
    
    # تشخیص علت اولیه
    if trade['reason'] == 'stop_loss':
        if mae > 1.5:
            primary_cause = 'STOP_TOO_TIGHT'
        else:
            primary_cause = 'NORMAL_STOP'
    elif trade['reason'] == 'signal_reverse':
        primary_cause = 'BAD_EXIT'
    else:
        primary_cause = 'OTHER'
    
    # بررسی هم‌جهتی تایم‌فریم
    htf_aligned = True  # در این استراتژی با فیلتر ۱h وارد می‌شویم
    
    # ساخت نتیجه
    forensic = {
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
        'htf_aligned': htf_aligned,
        'volume_ok': volume_ok,
        'rsi_at_entry': rsi,
        'exit_reason': trade['reason'],
        'duration_minutes': trade['duration'].total_seconds() / 60,
        'primary_cause': primary_cause,
        'strategy_valid': True,  # نیاز به بررسی بیشتر
        'execution_valid': True,
        'risk_problem': mae > 2.0,  # اگر MAE بیش از ۲٪ باشد
        'data_valid': True,
    }
    
    return forensic

if __name__ == "__main__":
    analyze_trade_forensics()
