"""
بکتست با فیلتر روند ۱ ساعته + ADX 30 + SL 3.5
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

def get_hourly_trend(client, symbol):
    """دریافت روند ۱ ساعته"""
    df_1h = client.get_candles(symbol, '1h', 200)
    if df_1h is None or len(df_1h) < 50:
        return 0
    
    ema_50 = df_1h['close'].ewm(span=50).mean()
    ema_200 = df_1h['close'].ewm(span=200).mean()
    
    if ema_50.iloc[-1] > ema_200.iloc[-1]:
        return 1
    elif ema_50.iloc[-1] < ema_200.iloc[-1]:
        return -1
    else:
        return 0

def main():
    print("🚀 بکتست با فیلتر روند ۱ ساعته + ADX 30 + SL 3.5")
    print("=" * 60)
    
    client = GateClient()
    strategy = TrendStateStrategy()
    
    # تغییر پارامترها
    strategy.config['adx_threshold'] = 30
    strategy.config['atr_mult_sl'] = 3.5
    
    all_results = []
    
    for symbol in ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT',
                   'DOGE_USDT', 'ADA_USDT', 'SUI_USDT', 'UNI_USDT', 'LINK_USDT',
                   'HYPE_USDT', 'ZEC_USDT']:
        
        try:
            hourly_trend = get_hourly_trend(client, symbol)
            
            if hourly_trend == 0:
                print(f"⏭️ {symbol}: روند ۱h خنثی - رد شد")
                continue
            
            trend_direction = "صعودی 📈" if hourly_trend == 1 else "نزولی 📉"
            print(f"\n🔍 {symbol} - روند ۱h: {trend_direction}")
            
            df = client.get_candles(symbol, '5m', 2000)
            
            if df is None or len(df) < 100:
                continue
            
            signals = strategy.generate_signals(df)
            
            # فیلتر جهت روند ۱ ساعته
            if hourly_trend == 1:
                signals['bear_signal'] = False
            else:
                signals['bull_signal'] = False
            
            engine = BacktestEngine(initial_capital=1000)
            results = engine.run_backtest(df, signals)
            
            print(f"   معاملات: {results['total_trades']}, موفقیت: {results['win_rate']:.1f}%, سود: {results['total_pnl']:.2f}")
            
            all_results.append({
                'symbol': symbol,
                'hourly_trend': hourly_trend,
                **results
            })
            
        except Exception as e:
            print(f"❌ {symbol}: {e}")
    
    if all_results:
        df_results = pd.DataFrame(all_results)
        df_results = df_results.sort_values('return_pct', ascending=False)
        
        print("\n" + "=" * 60)
        print("📊 نتایج با فیلتر روند ۱h + ADX 30 + SL 3.5:")
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
