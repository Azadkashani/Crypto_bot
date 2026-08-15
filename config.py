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

# لوریج قدیمی برای سازگاری با فازهای قبلی
LEVERAGE = 20

# --- Signal Scoring Weights ---
REGIME_SCORE_WEIGHT = 25
RSI_SCORE_WEIGHT = 20
CHOCH_SCORE_WEIGHT = 20
BOS_SCORE_WEIGHT = 20
VOLUME_SCORE_WEIGHT = 10
RR_SCORE_WEIGHT = 5

# --- Phase 19: Live / Paper Trading ---
PAPER_TRADING = True  # هرگز False نکن مگر با تایید صریح

SYMBOL_WHITELIST = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "HYPE/USDT:USDT",
    "BNB/USDT:USDT",
    "ZEC/USDT:USDT",
    "ADA/USDT:USDT",
    "UNI/USDT:USDT",
    "SUI/USDT:USDT",
    "LINK/USDT:USDT",
]

# --- Live Price Sync ---
MAX_ENTRY_PRICE_DEVIATION = 0.002   # حداکثر انحراف مجاز قیمت ورود از قیمت لحظه‌ای (0.2%)

# --- Trading Costs (Backtest Realism) ---
MAKER_FEE_RATE = 0.0002        # Fee سازنده
TAKER_FEE_RATE = 0.0005        # Fee گیرنده (برای سفارش‌های Market)
SLIPPAGE_BPS = 2               # ۲ بیس پوینت = 0.02%
SLIPPAGE_RATE = SLIPPAGE_BPS / 10000
ENABLE_FUNDING = False         # فعلاً فعال نمی‌شود؛ نیاز به داده تاریخی Funding دارد
