"""
فایل تست بکتست
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtest.backtest_engine import BacktestEngine
from strategy.trend_state import TrendStateStrategy

def create_test_data(candles: int = 1000):
    """ایجاد دادههای تست"""
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=candles, freq='5min')
    
    # ایجاد قیمت با روند
    prices = [100]
    for i in range(1, candles):
        if i % 200 < 100:
            change = np.random.normal(0.3, 1.0)
        elif i % 200 < 150:
            change = np.random.normal(-0.3, 1.0)
        else:
            change = np.random.normal(0, 0.5)
        prices.append(max(prices[-1] + change, 1))
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + np.random.uniform(0.001, 0.01)) for p in prices],
        'low': [p * (1 - np.random.uniform(0.001, 0.01)) for p in prices],
        'close': prices,
        'volume': np.random.uniform(1000, 10000, candles)
    }, index=dates)
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df

def main():
    print("=" * 60)
    print("🔍 تست بکتست")
    print("=" * 60)
    
    # ایجاد داده تست
    df = create_test_data(1000)
    print(f"✅ داده تست: {len(df)} کندل")
    
    # اجرای استراتژی
    strategy = TrendStateStrategy()
    signals = strategy.generate_signals(df)
    
    bull_signals = signals['bull_signal'].sum()
    bear_signals = signals['bear_signal'].sum()
    print(f"✅ سیگنال خرید: {bull_signals}")
    print(f"✅ سیگنال فروش: {bear_signals}")
    
    # اجرای بکتست
    engine = BacktestEngine(initial_capital=1000)
    results = engine.run_backtest(df, signals)
    
    print("\n📊 نتایج بکتست:")
    print(f"   تعداد معاملات: {results['total_trades']}")
    print(f"   معاملات سودده: {results['winning_trades']}")
    print(f"   معاملات ضررده: {results['losing_trades']}")
    print(f"   نرخ موفقیت: {results['win_rate']:.2f}%")
    print(f"   سود/ضرر کل: {results['total_pnl']:.2f} USDT")
    print(f"   سرمایه نهایی: {results['final_capital']:.2f} USDT")
    print(f"   بازدهی: {results['return_pct']:.2f}%")
    
    if results['total_trades'] > 0:
        print(f"   میانگین سود: {results['avg_win']:.2f} USDT")
        print(f"   میانگین ضرر: {results['avg_loss']:.2f} USDT")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
    
    print("\n" + "=" * 60)
    print("✅ تست بکتست با موفقیت انجام شد!")
    print("=" * 60)

if __name__ == "__main__":
    main()
