"""
پیکربندی ارزهای معاملاتی
"""

import pandas as pd

# لیست ارزهای معاملاتی با جزئیات
COINS_CONFIG = {
    'BTC': {
        'symbol': 'BTC_USDT',
        'name': 'Bitcoin',
        'min_order_size': 0.0001,  # حداقل حجم سفارش
        'price_precision': 2,       # دقت قیمت
        'quantity_precision': 6,    # دقت حجم
        'is_major': True,           # ارز اصلی (تاثیر بر سایر ارزها)
        'category': 'layer1',       # دسته‌بندی
        'weight': 1.0,              # وزن در امتیازدهی
    },
    'ETH': {
        'symbol': 'ETH_USDT',
        'name': 'Ethereum',
        'min_order_size': 0.001,
        'price_precision': 2,
        'quantity_precision': 5,
        'is_major': True,
        'category': 'layer1',
        'weight': 0.9,
    },
    'SOL': {
        'symbol': 'SOL_USDT',
        'name': 'Solana',
        'min_order_size': 0.01,
        'price_precision': 3,
        'quantity_precision': 4,
        'is_major': False,
        'category': 'layer1',
        'weight': 0.8,
    },
    'BNB': {
        'symbol': 'BNB_USDT',
        'name': 'Binance Coin',
        'min_order_size': 0.01,
        'price_precision': 2,
        'quantity_precision': 4,
        'is_major': False,
        'category': 'exchange_token',
        'weight': 0.8,
    },
    'XRP': {
        'symbol': 'XRP_USDT',
        'name': 'Ripple',
        'min_order_size': 1,
        'price_precision': 4,
        'quantity_precision': 2,
        'is_major': False,
        'category': 'payment',
        'weight': 0.7,
    },
    'DOGE': {
        'symbol': 'DOGE_USDT',
        'name': 'Dogecoin',
        'min_order_size': 10,
        'price_precision': 5,
        'quantity_precision': 1,
        'is_major': False,
        'category': 'meme',
        'weight': 0.6,
    },
    'ADA': {
        'symbol': 'ADA_USDT',
        'name': 'Cardano',
        'min_order_size': 1,
        'price_precision': 4,
        'quantity_precision': 2,
        'is_major': False,
        'category': 'layer1',
        'weight': 0.7,
    },
    'SUI': {
        'symbol': 'SUI_USDT',
        'name': 'Sui',
        'min_order_size': 0.1,
        'price_precision': 3,
        'quantity_precision': 2,
        'is_major': False,
        'category': 'layer1',
        'weight': 0.7,
    },
    'UNI': {
        'symbol': 'UNI_USDT',
        'name': 'Uniswap',
        'min_order_size': 0.1,
        'price_precision': 3,
        'quantity_precision': 2,
        'is_major': False,
        'category': 'defi',
        'weight': 0.7,
    },
    'LINK': {
        'symbol': 'LINK_USDT',
        'name': 'Chainlink',
        'min_order_size': 0.1,
        'price_precision': 3,
        'quantity_precision': 2,
        'is_major': False,
        'category': 'oracle',
        'weight': 0.7,
    },
    'HYPE': {
        'symbol': 'HYPE_USDT',
        'name': 'Hyperliquid',
        'min_order_size': 0.01,
        'price_precision': 2,
        'quantity_precision': 3,
        'is_major': False,
        'category': 'layer1',
        'weight': 0.6,
    },
    'ZEC': {
        'symbol': 'ZEC_USDT',
        'name': 'Zcash',
        'min_order_size': 0.01,
        'price_precision': 2,
        'quantity_precision': 3,
        'is_major': False,
        'category': 'privacy',
        'weight': 0.6,
    },
}

def get_coin_symbols():
    """دریافت لیست سیمبل‌های ارزها برای API"""
    return [config['symbol'] for config in COINS_CONFIG.values()]

def get_coin_names():
    """دریافت لیست نام ارزها برای اخبار"""
    return list(COINS_CONFIG.keys())

def get_coin_config(symbol):
    """دریافت تنظیمات یک ارز خاص"""
    for coin, config in COINS_CONFIG.items():
        if config['symbol'] == symbol:
            return coin, config
    return None, None

# ایجاد DataFrame برای نمایش
coins_df = pd.DataFrame(COINS_CONFIG).T
