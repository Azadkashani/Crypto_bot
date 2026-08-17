"""
فایل تست استراتژی Trend State
این فایل را در VPS اجرا کنید تا از صحت عملکرد استراتژی مطمئن شوید
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategy.trend_state import TrendStateStrategy

def create_sample_data(candles: int = 500) -> pd.DataFrame:
    """
    ایجاد داده‌های نمونه برای تست
    """
    np.random.seed(42)
    
    # ایجاد داده‌های قیمتی تصادفی با روند
    dates = pd.date_range(end=datetime.now(), periods=candles, freq='5min')
    
    # قیمت پایه
    base_price = 100
    prices = [base_price]
    
    for i in range(1, candles):
        # ایجاد روند با نوسان
        if i % 100 < 50:  # روند صعودی
            change = np.random.normal(0.5, 1.5)
        elif i % 100 < 80:  # روند نزولی
            change = np.random.normal(-0.5, 1.5)
        else:  # بازار رنج
            change = np.random.normal(0, 0.8)
        
        new_price = prices[-1] + change
        prices.append(max(new_price, 1))  # قیمت مثبت
    
    # ایجاد DataFrame
    df = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + np.random.uniform(0.001, 0.02)) for p in prices],
        'low': [p * (1 - np.random.uniform(0.001, 0.02)) for p in prices],
        'close': prices,
        'volume': np.random.uniform(100, 10000, candles)
    }, index=dates)
    
    # اصلاح high و low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df

def test_strategy_basic():
    """
    تست پایه استراتژی
    """
    print("=" * 60)
    print("تست پایه استراتژی Trend State")
    print("=" * 60)
    
    # ایجاد داده‌های نمونه
    df = create_sample_data(500)
    print(f"✅ داده‌های نمونه ایجاد شد: {len(df)} کندل")
    
    # ایجاد استراتژی
    strategy = TrendStateStrategy()
    print("✅ استراتژی ایجاد شد")
    
    # محاسبه سیگنال‌ها
    df_with_signals = strategy.generate_signals(df)
    print("✅ سیگنال‌ها محاسبه شدند")
    
    # بررسی نتایج
    bull_signals = df_with_signals['bull_signal'].sum()
    bear_signals = df_with_signals['bear_signal'].sum()
    
    print(f"\n📊 نتایج:")
    print(f"   سیگنال‌های خرید: {bull_signals}")
    print(f"   سیگنال‌های فروش: {bear_signals}")
    
    # بررسی صحت محاسبات
    assert 'filter_line' in df_with_signals.columns, "❌ خط فیلتر محاسبه نشده"
    assert 'trend' in df_with_signals.columns, "❌ روند محاسبه نشده"
    assert 'bull_signal' in df_with_signals.columns, "❌ سیگنال خرید محاسبه نشده"
    assert 'bear_signal' in df_with_signals.columns, "❌ سیگنال فروش محاسبه نشده"
    
    print("✅ تمام محاسبات انجام شد")
    
    # نمایش چند سیگنال نمونه
    if bull_signals > 0:
        first_bull = df_with_signals[df_with_signals['bull_signal']].iloc[0]
        print(f"\n🎯 نمونه سیگنال خرید:")
        print(f"   زمان: {df_with_signals[df_with_signals['bull_signal']].index[0]}")
        print(f"   قیمت: {first_bull['close']:.2f}")
        print(f"   روند: {first_bull['trend']}")
        print(f"   ADX: {first_bull.get('adx', 'N/A'):.2f}" if 'adx' in first_bull else "")
    
    return df_with_signals

def test_filters():
    """
    تست فیلترهای مختلف
    """
    print("\n" + "=" * 60)
    print("تست فیلترهای استراتژی")
    print("=" * 60)
    
    df = create_sample_data(500)
    strategy = TrendStateStrategy()
    df_with_signals = strategy.generate_signals(df)
    
    # تست فیلتر روند
    if 'trend_ma' in df_with_signals.columns:
        trend_filter_active = df_with_signals['trend_ok_long'].sum()
        print(f"✅ فیلتر روند فعال: {trend_filter_active} کندل صعودی")
    
    # تست فیلتر ADX
    if 'adx' in df_with_signals.columns:
        adx_filter_active = df_with_signals['adx_ok'].sum()
        print(f"✅ فیلتر ADX فعال: {adx_filter_active} کندل با ADX بالا")
    
    # تست فیلتر نوسان
    if 'vol_ok' in df_with_signals.columns:
        vol_filter_active = df_with_signals['vol_ok'].sum()
        print(f"✅ فیلتر نوسان فعال: {vol_filter_active} کندل با نوسان مناسب")
    
    # تست فیلتر Bollinger
    if 'bb_ok' in df_with_signals.columns:
        bb_filter_active = df_with_signals['bb_ok'].sum()
        bb_squeeze_count = df_with_signals['bb_squeeze'].sum()
        print(f"✅ فیلتر Bollinger: {bb_filter_active} کندل مناسب")
        print(f"   کندل‌های Squeeze: {bb_squeeze_count} (فیلتر شده)")
    
    return df_with_signals

def test_risk_management():
    """
    تست مدیریت ریسک
    """
    print("\n" + "=" * 60)
    print("تست مدیریت ریسک")
    print("=" * 60)
    
    df = create_sample_data(500)
    strategy = TrendStateStrategy()
    df_with_signals = strategy.generate_signals(df)
    
    # بررسی حد ضرر و سود
    if 'long_stop' in df_with_signals.columns and 'long_tp' in df_with_signals.columns:
        # محاسبه میانگین فاصله حد ضرر و سود
        avg_stop_distance = (df_with_signals['close'] - df_with_signals['long_stop']).mean()
        avg_tp_distance = (df_with_signals['long_tp'] - df_with_signals['close']).mean()
        
        print(f"✅ میانگین فاصله حد ضرر: {avg_stop_distance:.2f}")
        print(f"✅ میانگین فاصله حد سود: {avg_tp_distance:.2f}")
        print(f"✅ نسبت ریسک به ریوارد: {avg_tp_distance/avg_stop_distance:.2f}")
    
    return df_with_signals

def main():
    """
    اجرای تمام تست‌ها
    """
    print("\n🔍 شروع تست استراتژی Trend State")
    print("=" * 60)
    
    try:
        # تست 1: تست پایه
        df_signals = test_strategy_basic()
        
        # تست 2: تست فیلترها
        df_filters = test_filters()
        
        # تست 3: تست مدیریت ریسک
        df_risk = test_risk_management()
        
        print("\n" + "=" * 60)
        print("✅ تمام تست‌ها با موفقیت انجام شد!")
        print("=" * 60)
        
        # ذخیره نتایج برای بررسی
        output_file = 'test_results_strategy.csv'
        df_signals.to_csv(output_file)
        print(f"\n📁 نتایج در فایل '{output_file}' ذخیره شد")
        
    except Exception as e:
        print(f"\n❌ خطا در تست: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
