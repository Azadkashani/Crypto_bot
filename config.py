"""
پیکربندی پروژه Crypto AI Trader V2.
تمامی مقادیر باید از طریق این فایل مدیریت شوند.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# صرافی
EXCHANGE_ID = 'gateio'
EXCHANGE_OPTIONS = {
    'defaultType': 'swap',  # perpetual futures
    'apiKey': os.getenv('GATEIO_API_KEY', ''),
    'secret': os.getenv('GATEIO_SECRET', ''),
}

# نماد معاملاتی (USDT-M perpetual)
SYMBOL = 'BTC/USDT:USDT'

# تایم‌فریم‌ها
TIMEFRAMES = ['4h', '1h', '5m']

# آستانه‌های RSI
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_PERIOD = 14

# آستانه امتیاز
SCORE_THRESHOLD_LONG = 7
SCORE_THRESHOLD_SHORT = 7

# مسیر ذخیره داده‌ها
DATA_DIR = 'data/'

# تنظیمات عمومی
UTC = True

# --- اندیکاتورها ---
EMA_SHORT = 9
EMA_LONG = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14
VOLUME_SMA_PERIOD = 20
SWING_LEFT_BARS = 3
SWING_RIGHT_BARS = 3

# --- رژیم بازار ---
EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200
ADX_MIN_TREND = 20

# --- تایم‌فریم‌های سیگنال ---
TIMEFRAME_4H = '4h'
TIMEFRAME_1H = '1h'
TIMEFRAME_5M = '5m'

# --- Risk Gate ---
RISK_REWARD = 2.0

# --- Position Sizing / Portfolio ---
RISK_PER_TRADE = 0.01          # ۱٪ کل سرمایه
POSITION_ALLOCATION = 0.25     # ۲۵٪ سرمایه برای هر معامله
MAX_LEVERAGE = 20              # حداکثر لوریج مجاز
MAX_CONCURRENT_POSITIONS = 4   # حداکثر ۴ پوزیشن همزمان
MAX_TOTAL_RISK = 0.04          # حداکثر ریسک کل ۴٪
ACCOUNT_BALANCE = 1000.0

# لوریج قدیمی برای حفظ سازگاری با فازهای قبلی
LEVERAGE = 20