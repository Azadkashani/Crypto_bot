"""
بکتست واقعی با تایمفریم ۱ ساعته
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
import logging

from exchange.gate_client import GateClient
from strategy.trend_state import TrendStateStrategy
from backtest.backtest_engine import BacktestEngine
from config.settings import TRADING_COINS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_backtest_for_coin(client, strategy, engine, symbol, timeframe='1h', limit=2000):
    """اجرای بکتست برای یک ارز"""
    print(f"\n{'='*60}")
    print(f"🔍 بکتست {symbol} - تایمفریم {timeframe}")
    print(f"{'='*60}")
    
    # دریافت داده‌ها
    df = client.get_candles(symbol, timeframe, limit)
    
    if df is None or len(df) < 100:
        print(f"❌ داده کافی برای {symbol} وجود ندارد")
        return None
    
    print(f"✅ دریافت {len(df)} کندل")
    
    # اجرای استراتژی
    signals = strategy.generate_signals(df)
    
    bull_signals = signals['bull_signal'].sum()
    bear_signals = signals['bear_signal'].sum()
    
    print(f"✅ سیگنال خرید: {bull_signals}")
    print(f"✅ سیگنال فروش: {bear_signals}")
    
    # اجرای بکتست
    engine = BacktestEngine(initial_capital=1000)
    results = engine.run_backtest(df, signals)
    
    print(f"\n📊 نتایج:")
    print(f"   معاملات: {results['total_trades']}")
    print(f"   موفقیت: {results['win_rate']:.2f}%")
    print(f"   سود/ضرر: {results['total_pnl']:.2f} USDT")
    print(f"   بازدهی: {results['return_pct']:.2f}%")
    
    return {
        'symbol': symbol,
        'candles': len(df),
        'bull_signals': bull_signals,
        'bear_signals': bear_signals,
        **results
    }

def main():
    print("🚀 شروع بکتست واقعی با تایمفریم ۱ ساعته")
    print("=" * 60)
    
    # ساخت کلاینت (بدون API Key برای داده عمومی)
    client = GateClient()
    
    # ساخت استراتژی
    strategy = TrendStateStrategy()
    
    # نتایج تمام ارزها
    all_results = []
    
    # اجرای بکتست برای هر ارز
    for symbol in TRADING_COINS:
        try:
            engine = BacktestEngine(initial_capital=1000)
            result = run_backtest_for_coin(client, strategy, engine, symbol, timeframe='1h')
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"❌ خطا برای {symbol}: {e}")
    
    # نمایش خلاصه
    print("\n" + "=" * 60)
    print("📊 خلاصه نتایج تمام ارزها - تایمفریم ۱ ساعته")
    print("=" * 60)
    
    if all_results:
        df_results = pd.DataFrame(all_results)
        df_results = df_results.sort_values('return_pct', ascending=False)
        
        print("\n🔝 بهترین ارزها:")
        print(df_results[['symbol', 'total_trades', 'win_rate', 'return_pct']].head(5).to_string(index=False))
        
        print("\n📉 ضعیف‌ترین ارزها:")
        print(df_results[['symbol', 'total_trades', 'win_rate', 'return_pct']].tail(5).to_string(index=False))
        
        # ذخیره نتایج
        df_results.to_csv('backtest_results_1h.csv', index=False)
        print(f"\n📁 نتایج در backtest_results_1h.csv ذخیره شد")
        
        # آمار کلی
        total_trades = df_results['total_trades'].sum()
        avg_win_rate = df_results['win_rate'].mean()
        total_pnl = df_results['total_pnl'].sum()
        
        print(f"\n📊 آمار کلی:")
        print(f"   کل معاملات: {total_trades}")
        print(f"   میانگین موفقیت: {avg_win_rate:.2f}%")
        print(f"   سود/ضرر کل: {total_pnl:.2f} USDT")
    else:
        print("❌ هیچ نتیجه‌ای تولید نشد")

if __name__ == "__main__":
    main()
