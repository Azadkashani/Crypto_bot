"""
بکتست استراتژی جدید EMA + RSI
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

def main():
    print("🚀 بکتست استراتژی EMA + RSI")
    print("=" * 60)
    
    client = GateClient()
    strategy = TrendStateStrategy()
    
    all_results = []
    
    for symbol in ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT',
                   'DOGE_USDT', 'ADA_USDT', 'SUI_USDT', 'UNI_USDT', 'LINK_USDT',
                   'HYPE_USDT', 'ZEC_USDT']:
        
        try:
            print(f"\n🔍 {symbol}")
            
            # دریافت داده ۱ ساعته
            df_1h = client.get_candles(symbol, '1h', 200)
            
            # دریافت داده ۵ دقیقه
            df_5m = client.get_candles(symbol, '5m', 2000)
            
            if df_5m is None or len(df_5m) < 100:
                continue
            
            # اجرای استراتژی با داده ۱ ساعته
            signals = strategy.generate_signals(df_5m, df_1h)
            
            # اجرای بکتست
            engine = BacktestEngine(initial_capital=1000)
            results = engine.run_backtest(df_5m, signals)
            
            print(f"   سیگنال خرید: {signals['bull_signal'].sum()}")
            print(f"   سیگنال فروش: {signals['bear_signal'].sum()}")
            print(f"   معاملات: {results['total_trades']}, موفقیت: {results['win_rate']:.1f}%, سود: {results['total_pnl']:.2f}")
            
            all_results.append({
                'symbol': symbol,
                **results
            })
            
        except Exception as e:
            print(f"❌ {symbol}: {e}")
    
    if all_results:
        df_results = pd.DataFrame(all_results)
        df_results = df_results.sort_values('return_pct', ascending=False)
        
        print("\n" + "=" * 60)
        print("📊 نتایج استراتژی EMA + RSI:")
        print(df_results[['symbol', 'total_trades', 'win_rate', 'return_pct']].to_string(index=False))
        
        total_pnl = df_results['total_pnl'].sum()
        avg_win_rate = df_results['win_rate'].mean()
        total_trades = df_results['total_trades'].sum()
        
        print(f"\n📊 آمار کلی:")
        print(f"   کل معاملات: {total_trades}")
        print(f"   میانگین موفقیت: {avg_win_rate:.1f}%")
        print(f"   سود/ضرر کل: {total_pnl:.2f} USDT")

if __name__ == "__main__":
    main()
