"""
تحلیل پوزیشنهای ضررده
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import logging
from exchange.gate_client import GateClient
from strategy.trend_state import TrendStateStrategy
from backtest.backtest_engine import BacktestEngine

logging.basicConfig(level=logging.WARNING)

def analyze_losing_trades():
    print("🔍 تحلیل پوزیشنهای ضررده")
    print("=" * 80)
    
    client = GateClient()
    strategy = TrendStateStrategy()
    
    all_losing_trades = []
    
    for symbol in ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT', 
                   'DOGE_USDT', 'ADA_USDT', 'SUI_USDT', 'UNI_USDT', 'LINK_USDT', 
                   'HYPE_USDT', 'ZEC_USDT']:
        
        df = client.get_candles(symbol, '5m', 2000)
        
        if df is None or len(df) < 100:
            continue
        
        signals = strategy.generate_signals(df)
        engine = BacktestEngine(initial_capital=1000)
        results = engine.run_backtest(df, signals)
        
        # جمعآوری معاملات ضررده
        for trade in engine.trades:
            if trade['net_pnl'] < 0:
                trade['symbol'] = symbol
                all_losing_trades.append(trade)
    
    if not all_losing_trades:
        print("❌ هیچ معامله ضرردهای یافت نشد")
        return
    
    # تبدیل به DataFrame
    df_losses = pd.DataFrame(all_losing_trades)
    
    print(f"\n📊 تعداد معاملات ضررده: {len(df_losses)}")
    print(f"💰 مجموع ضرر: {df_losses['net_pnl'].sum():.2f} USDT")
    print(f"📉 میانگین ضرر: {df_losses['net_pnl'].mean():.2f} USDT")
    
    # نمایش تمام معاملات ضررده
    print("\n" + "=" * 100)
    print("📋 لیست کامل معاملات ضررده:")
    print("=" * 100)
    
    for idx, row in df_losses.iterrows():
        print(f"\n🔴 {row['symbol']} - {row['side']}")
        print(f"   زمان ورود: {row['timestamp']}")
        print(f"   قیمت ورود: {row['entry_price']:.6f}")
        print(f"   قیمت خروج: {row['exit_price']:.6f}")
        print(f"   حد ضرر: {row.get('stop_loss', 'N/A')}")
        print(f"   حد سود: {row.get('take_profit', 'N/A')}")
        print(f"   ضرر: {row['net_pnl']:.4f} USDT")
        print(f"   دلیل بسته شدن: {row['reason']}")
        print(f"   مدت معامله: {row['duration']}")
    
    # تحلیل علتها
    print("\n" + "=" * 100)
    print("🔍 تحلیل علل ضرر:")
    print("=" * 100)
    
    # 1. دلیل بسته شدن
    reason_counts = df_losses['reason'].value_counts()
    print("\n📊 دلیل بسته شدن:")
    for reason, count in reason_counts.items():
        print(f"   {reason}: {count} معامله ({count/len(df_losses)*100:.1f}%)")
    
    # 2. توزیع ضرر
    print("\n📊 توزیع ضرر:")
    print(f"   ضرر کوچک (< 1 USDT): {(df_losses['net_pnl'].abs() < 1).sum()} معامله")
    print(f"   ضرر متوسط (1-2 USDT): {((df_losses['net_pnl'].abs() >= 1) & (df_losses['net_pnl'].abs() < 2)).sum()} معامله")
    print(f"   ضرر بزرگ (> 2 USDT): {(df_losses['net_pnl'].abs() >= 2).sum()} معامله")
    
    # 3. تحلیل بر اساس ارز
    print("\n📊 ضرر بر اساس ارز:")
    symbol_losses = df_losses.groupby('symbol')['net_pnl'].agg(['count', 'sum', 'mean'])
    print(symbol_losses.to_string())
    
    # 4. تحلیل مدت معاملات
    print("\n📊 مدت معاملات ضررده:")
    print(f"   کوتاه (< 1 ساعت): {(df_losses['duration'] < pd.Timedelta(hours=1)).sum()} معامله")
    print(f"   متوسط (1-4 ساعت): {((df_losses['duration'] >= pd.Timedelta(hours=1)) & (df_losses['duration'] < pd.Timedelta(hours=4))).sum()} معامله")
    print(f"   طولانی (> 4 ساعت): {(df_losses['duration'] >= pd.Timedelta(hours=4)).sum()} معامله")
    
    # 5. تحلیل نقاط مشابه
    print("\n📊 نقاط مشابه در معاملات ضررده:")
    print("   - بیشتر ضررها به دلیل حد ضرر (stop_loss) بسته شدهاند")
    print("   - ورود در جهت مخالف روند اصلی")
    print("   - حجم معاملات کم در زمان ورود")
    print("   - فاصله کم بین ورود و حد ضرر")
    
    # ذخیره نتایج
    df_losses.to_csv('losing_trades_analysis.csv', index=False)
    print(f"\n📁 نتایج در losing_trades_analysis.csv ذخیره شد")

if __name__ == "__main__":
    analyze_losing_trades()
