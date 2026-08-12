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

# آستانه‌های RSI (برای آینده)
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_PERIOD = 14

# آستانه امتیاز (برای فازهای بعدی)
SCORE_THRESHOLD_LONG = 7
SCORE_THRESHOLD_SHORT = 7

# مسیر ذخیره داده‌ها
DATA_DIR = 'data/'

# تنظیمات عمومی
UTC = True
