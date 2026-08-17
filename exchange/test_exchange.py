"""
فایل تست اتصال به صرافی Gate.io
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange.gate_client import GateClient
from config.settings import GATE_API_KEY, GATE_API_SECRET, TRADING_COINS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """تست اتصال به API"""
    print("=" * 60)
    print("🔍 تست اتصال به Gate.io")
    print("=" * 60)
    
    # ساخت کلاینت
    client = GateClient(GATE_API_KEY, GATE_API_SECRET)
    
    # تست اتصال
    if client.test_connection():
        print("✅ اتصال به Gate.io برقرار شد")
        return client
    else:
        print("❌ اتصال برقرار نشد")
        return None

def test_account_balance(client):
    """تست دریافت موجودی"""
    print("\n" + "=" * 60)
    print("💰 تست دریافت موجودی")
    print("=" * 60)
    
    balance = client.get_account_balance()
    
    if balance:
        print(f"✅ موجودی کل: {balance['total']:.2f} USDT")
        print(f"✅ موجودی قابل استفاده: {balance['available']:.2f} USDT")
        print(f"✅ سود/ضرر باز: {balance['unrealised_pnl']:.2f} USDT")
        return balance
    else:
        print("❌ خطا در دریافت موجودی")
        return None

def test_get_candles(client):
    """تست دریافت کندل‌ها"""
    print("\n" + "=" * 60)
    print("📊 تست دریافت کندل‌ها")
    print("=" * 60)
    
    # تست برای BTC
    symbol = "BTC_USDT"
    timeframe = "5m"
    
    df = client.get_candles(symbol, timeframe, limit=100)
    
    if df is not None and len(df) > 0:
        print(f"✅ دریافت {len(df)} کندل برای {symbol}")
        print(f"\n📊 نمونه داده:")
        print(df.head())
        print(f"\n📊 آخرین کندل:")
        print(df.tail(1))
        return df
    else:
        print("❌ خطا در دریافت کندل‌ها")
        return None

def test_get_ticker(client):
    """تست دریافت قیمت لحظه‌ای"""
    print("\n" + "=" * 60)
    print("💹 تست دریافت قیمت لحظه‌ای")
    print("=" * 60)
    
    ticker = client.get_ticker("BTC_USDT")
    
    if ticker:
        print(f"✅ قیمت آخر BTC: {ticker['last_price']:.2f} USDT")
        print(f"✅ حجم 24h: {ticker['volume_24h_quote']:.2f} USDT")
        print(f"✅ نرخ فاندینگ: {ticker['funding_rate']*100:.4f}%")
        return ticker
    else:
        print("❌ خطا در دریافت قیمت")
        return None

def test_all_coins(client):
    """تست دریافت اطلاعات تمام ارزها"""
    print("\n" + "=" * 60)
    print("🪙 تست دریافت اطلاعات ۱۲ ارز")
    print("=" * 60)
    
    for symbol in TRADING_COINS:
        try:
            ticker = client.get_ticker(symbol)
            if ticker:
                volume_million = ticker['volume_24h_quote'] / 1_000_000
                print(f"✅ {symbol}: قیمت={ticker['last_price']:.4f}, حجم={volume_million:.1f}M USDT")
            else:
                print(f"⚠️ {symbol}: خطا")
        except Exception as e:
            print(f"❌ {symbol}: {e}")

def main():
    """اجرای تمام تست‌ها"""
    print("\n🔍 شروع تست اتصال به Gate.io")
    print("=" * 60)
    
    # تست اتصال
    client = test_connection()
    if not client:
        return
    
    # تست موجودی
    balance = test_account_balance(client)
    
    # تست کندل‌ها
    df = test_get_candles(client)
    
    # تست قیمت
    ticker = test_get_ticker(client)
    
    # تست تمام ارزها
    test_all_coins(client)
    
    print("\n" + "=" * 60)
    if balance and df is not None and ticker:
        print("✅ تمام تست‌ها با موفقیت انجام شد!")
    else:
        print("⚠️ برخی تست‌ها ناموفق بودند")
    print("=" * 60)

if __name__ == "__main__":
    main()
