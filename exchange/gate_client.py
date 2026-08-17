"""
کلاینت اتصال به صرافی Gate.io
"""

import gate_api
from gate_api.exceptions import ApiException, GateApiException
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# تنظیم لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GateClient:
    """
    کلاس ارتباط با API صرافی Gate.io
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """
        مقداردهی اولیه کلاینت
        
        Parameters:
        -----------
        api_key : str
            کلید API از Gate.io
        api_secret : str
            کلید مخفی API از Gate.io
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # پیکربندی کلاینت
        configuration = gate_api.Configuration(
            host="https://api.gateio.ws/api/v4",
            key=api_key,
            secret=api_secret
        )
        
        # ایجاد کلاینت‌ها
        self.api_client = gate_api.ApiClient(configuration)
        self.futures_api = gate_api.FuturesApi(self.api_client)
        self.spot_api = gate_api.SpotApi(self.api_client)
        
    def test_connection(self) -> bool:
        """
        تست اتصال به API
        """
        try:
            # دریافت زمان سرور
            response = self.spot_api.list_currencies()
            logger.info("✅ اتصال به Gate.io برقرار شد")
            return True
        except GateApiException as ex:
            logger.error(f"❌ خطای API: {ex}")
            return False
        except Exception as ex:
            logger.error(f"❌ خطای اتصال: {ex}")
            return False
    
    def get_account_balance(self) -> Dict:
        """
        دریافت موجودی حساب فیوچرز
        """
        try:
            # دریافت حساب فیوچرز
            account = self.futures_api.list_futures_accounts("usdt")
            
            return {
                'total': float(account.total),
                'available': float(account.available),
                'unrealised_pnl': float(account.unrealised_pnl),
                'position_margin': float(account.position_margin),
                'order_margin': float(account.order_margin)
            }
        except GateApiException as ex:
            logger.error(f"❌ خطا در دریافت موجودی: {ex}")
            return None
    
    def get_candles(self, symbol: str, timeframe: str = "5m", limit: int = 2000) -> pd.DataFrame:
        """
        دریافت کندل‌های قیمتی
        
        Parameters:
        -----------
        symbol : str
            نماد معاملاتی مثل "BTC_USDT"
        timeframe : str
            تایم‌فریم مثل "5m", "1h", "1d"
        limit : int
            تعداد کندل‌ها (حداکثر 2000)
            
        Returns:
        --------
        pd.DataFrame
            دیتافریم کندل‌ها با ستون‌های open, high, low, close, volume
        """
        try:
            # دریافت کندل‌ها
            candles = self.futures_api.list_futures_candlesticks(
                settle="usdt",
                contract=symbol,
                interval=timeframe,
                limit=limit
            )
            
            # تبدیل به DataFrame
            df = pd.DataFrame([{
                'timestamp': pd.to_datetime(candle.t, unit='s'),
                'open': float(candle.o),
                'high': float(candle.h),
                'low': float(candle.l),
                'close': float(candle.c),
                'volume': float(candle.v),
                'quote_volume': float(candle.sum)
            } for candle in candles])
            
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"✅ دریافت {len(df)} کندل برای {symbol}")
            return df
            
        except GateApiException as ex:
            logger.error(f"❌ خطا در دریافت کندل‌ها: {ex}")
            return None
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        دریافت قیمت لحظه‌ای
        """
        try:
            ticker = self.futures_api.list_futures_tickers(
                settle="usdt",
                contract=symbol
            )
            
            if ticker and len(ticker) > 0:
                return {
                    'symbol': symbol,
                    'last_price': float(ticker[0].last),
                    'mark_price': float(ticker[0].mark_price),
                    'index_price': float(ticker[0].index_price),
                    'volume_24h': float(ticker[0].volume_24h),
                    'volume_24h_quote': float(ticker[0].volume_24h_quote),
                    'funding_rate': float(ticker[0].funding_rate),
                    'high_24h': float(ticker[0].high_24h),
                    'low_24h': float(ticker[0].low_24h),
                }
            
        except GateApiException as ex:
            logger.error(f"❌ خطا در دریافت قیمت: {ex}")
            return None
    
    def get_open_positions(self) -> List[Dict]:
        """
        دریافت پوزیشن‌های باز
        """
        try:
            positions = self.futures_api.list_positions("usdt")
            
            open_positions = []
            for pos in positions:
                if float(pos.size) != 0:
                    open_positions.append({
                        'contract': pos.contract,
                        'size': float(pos.size),
                        'entry_price': float(pos.entry_price),
                        'mark_price': float(pos.mark_price),
                        'unrealised_pnl': float(pos.unrealised_pnl),
                        'leverage': float(pos.leverage),
                        'margin': float(pos.margin),
                        'liq_price': float(pos.liq_price) if pos.liq_price else None,
                    })
            
            return open_positions
            
        except GateApiException as ex:
            logger.error(f"❌ خطا در دریافت پوزیشن‌ها: {ex}")
            return []
    
    def get_contract_info(self, symbol: str) -> Dict:
        """
        دریافت اطلاعات قرارداد
        """
        try:
            contract = self.futures_api.get_futures_contract(
                settle="usdt",
                contract=symbol
            )
            
            return {
                'symbol': symbol,
                'quanto_multiplier': float(contract.quanto_multiplier),
                'order_size_min': float(contract.order_size_min),
                'order_size_max': float(contract.order_size_max),
                'mark_price_round': int(contract.mark_price_round),
                'leverage_min': float(contract.leverage_min),
                'leverage_max': float(contract.leverage_max),
                'funding_rate': float(contract.funding_rate) if contract.funding_rate else 0,
            }
            
        except GateApiException as ex:
            logger.error(f"❌ خطا در دریافت اطلاعات قرارداد: {ex}")
            return None
