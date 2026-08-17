"""
تنظیمات اصلی ربات معاملاتی Gate.io Futures
"""

import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

# ============================ API Configuration ============================
GATE_API_KEY = os.getenv('GATE_API_KEY')
GATE_API_SECRET = os.getenv('GATE_API_SECRET')
GATE_API_PASSPHRASE = os.getenv('GATE_API_PASSPHRASE', '')  # اگر نیاز است

# تنظیمات API
API_CONFIG = {
    'api_key': GATE_API_KEY,
    'api_secret': GATE_API_SECRET,
    'host': 'https://api.gateio.ws',
    'prefix': '/api/v4',
    'timeout': 30,
    'retry_count': 3,
}

# ============================ Trading Configuration ============================
TRADING_CONFIG = {
    # تایم‌فریم‌ها
    'primary_timeframe': '5m',      # تایم‌فریم اصلی معاملات
    'confirmation_timeframe': '1h',  # تایم‌فریم تایید
    
    # محدودیت‌های معاملاتی
    'max_concurrent_positions': 4,   # حداکثر ۴ معامله همزمان
    'position_size_percent': 25,     # ۲۵٪ موجودی برای هر معامله
    'max_positions_per_coin': 1,     # یک پوزیشن همزمان روی هر ارز
    
    # مدیریت ریسک
    'risk_per_trade_percent': 1,     # ۱٪ ریسک از کل سرمایه
    'risk_per_position_percent': 4,  # ۴٪ ریسک از حجم معامله
    'min_risk_reward_ratio': 2.0,    # حداقل نسبت ریسک به ریوارد
    'max_leverage': 20,              # حداکثر لوریج مجاز
    'min_leverage': 1,               # حداقل لوریج
    
    # فیلترهای حجم
    'min_daily_volume_usdt': 1_000_000,  # حداقل حجم معاملات روزانه
    
    # Cooldown
    'cooldown_bars': 3,  # حداقل فاصله بین سیگنال‌ها
}

# ============================ Strategy Configuration ============================
STRATEGY_CONFIG = {
    # هسته فیلتر
    'length': 14,
    'multiplier': 2.5,
    'offset': 0.5,
    'sigma': 1,
    'source_type': 'custom',
    
    # فیلتر روند
    'use_trend_filter': True,
    'trend_ma_len': 200,
    
    # فیلتر ADX
    'use_adx_filter': True,
    'adx_len': 14,
    'adx_threshold': 20,
    
    # فیلتر نوسان
    'use_vol_filter': True,
    'vol_len': 50,
    'vol_ratio_min': 0.8,
    'vol_ratio_max': 1.5,
    
    # فیلتر Bollinger Squeeze
    'use_bb_filter': True,
    'bb_len': 20,
    'bb_mult': 2.0,
    'bb_squeeze_threshold': 0.8,
    
    # مدیریت ریسک
    'use_atr_stop': True,
    'atr_len': 14,
    'atr_mult_sl': 2.5,
    'use_atr_tp': True,
    'atr_mult_tp': 4.0,
    'allow_short': True,
}

# ============================ Signal Scoring Configuration ============================
SIGNAL_SCORING_CONFIG = {
    'weights': {
        'timeframe_alignment': 0.25,    # هم‌جهتی تایم‌فریم‌ها
        'market_sentiment': 0.15,       # احساسات بازار (Fear & Greed)
        'risk_reward_ratio': 0.20,      # نسبت ریسک به ریوارد
        'news_impact': 0.15,            # تاثیر اخبار
        'indicator_confirmation': 0.15, # تایید اندیکاتورها
        'trend_strength': 0.10,         # قدرت روند
    },
    'min_score_to_trade': 0.70,  # حداقل امتیاز برای انجام معامله (۷۰٪)
    
    # Fear & Greed Index
    'fear_greed_extreme_fear': 25,   # ترس شدید
    'fear_greed_fear': 40,           # ترس
    'fear_greed_neutral': 60,        # خنثی
    'fear_greed_greed': 75,          # طمع
    'fear_greed_extreme_greed': 75,  # طمع شدید (بیشتر از این مقدار)
}

# ============================ Coin List ============================
TRADING_COINS = [
    'BTC_USDT',
    'ETH_USDT',
    'SOL_USDT',
    'BNB_USDT',
    'XRP_USDT',
    'DOGE_USDT',
    'ADA_USDT',
    'SUI_USDT',
    'UNI_USDT',
    'LINK_USDT',
    'HYPE_USDT',
    'ZEC_USDT',
]

# ============================ News Configuration ============================
NEWS_CONFIG = {
    'source': 'coingecko',
    'api_url': 'https://api.coingecko.com/api/v3',
    'max_age_hours': 2,  # حداکثر سن خبر (ساعت)
    'refresh_interval_minutes': 15,  # بازه بررسی اخبار (دقیقه)
}

# ============================ Fear & Greed Index ============================
FEAR_GREED_CONFIG = {
    'api_url': 'https://api.alternative.me/fng/',
    'refresh_interval_minutes': 30,
}

# ============================ Backtesting Configuration ============================
BACKTEST_CONFIG = {
    'candles_per_coin': 2000,  # حداکثر کندل قابل دانلود از Gate.io
    'initial_capital': 1000,    # سرمایه اولیه برای بک‌تست (USDT)
    'commission_rate': 0.0005,  # کارمزد معاملات (۰.۰۵٪)
    'slippage': 0.0002,         # اسلیپیج (۰.۰۲٪)
}

# ============================ Logging Configuration ============================
LOGGING_CONFIG = {
    'log_dir': 'logs',
    'log_file': 'trading_bot.log',
    'log_level': 'INFO',
    'rotation': '1 day',
    'retention': '30 days',
}
