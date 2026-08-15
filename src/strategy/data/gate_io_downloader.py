# FILE: src/strategy/data/gate_io_downloader.py

"""
Gate.io Historical Data Downloader
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import time
import requests


class GateIODownloadError(Exception):
    """خطای دانلود از Gate.io"""
    pass


@dataclass
class GateIODownloadConfig:
    """پیکربندی دانلود از Gate.io"""
    base_url: str = "https://api.gateio.ws"
    api_version: str = "api/v4"
    rate_limit_delay: float = 0.2  # ثانیه بین درخواست‌ها
    max_candles_per_request: int = 1000
    timeout: int = 30
    max_retries: int = 3


class GateIODownloader:
    """
    دانلود داده تاریخی OHLCV از Gate.io Futures
    
    از API عمومی Gate.io برای دریافت کندل‌های تاریخی استفاده می‌کند.
    """
    
    def __init__(self, config: Optional[GateIODownloadConfig] = None):
        self.config = config or GateIODownloadConfig()
        self.session = requests.Session()
    
    def fetch_ohlcv(
        self,
        symbol: str = "BTC_USDT",
        timeframe: str = "1h",
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        دریافت کندل‌های OHLCV از Gate.io Futures
        
        Args:
            symbol: نماد معاملاتی (مثلاً BTC_USDT)
            timeframe: تایم‌فریم (مثلاً 1h)
            start_timestamp: شروع بازه (unix seconds)
            end_timestamp: پایان بازه (unix seconds)
        
        Returns:
            لیست کندل‌ها
        """
        all_candles = []
        
        if end_timestamp is None:
            end_timestamp = int(time.time())
        
        if start_timestamp is None:
            # پیش‌فرض: 6 ماه قبل
            start_timestamp = end_timestamp - (180 * 24 * 3600)
        
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            batch = self._fetch_batch(
                symbol=symbol,
                timeframe=timeframe,
                start_ts=current_start,
                end_ts=end_timestamp
            )
            
            if not batch:
                break
            
            all_candles.extend(batch)
            
            # به‌روزرسانی start برای batch بعدی
            last_ts = batch[-1]['timestamp'] if batch else current_start
            current_start = last_ts + self._get_interval_seconds(timeframe)
            
            # Rate limit
            time.sleep(self.config.rate_limit_delay)
        
        # حذف duplicate
        seen = set()
        unique_candles = []
        
        for candle in all_candles:
            ts = candle['timestamp']
            if ts not in seen:
                seen.add(ts)
                unique_candles.append(candle)
        
        # مرتب‌سازی
        unique_candles.sort(key=lambda c: c['timestamp'])
        
        return unique_candles
    
    def _fetch_batch(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> List[Dict[str, Any]]:
        """دریافت یک batch از کندل‌ها"""
        url = f"{self.config.base_url}/{self.config.api_version}/futures/usdt/candlesticks"
        
        params = {
            'contract': symbol,
            'interval': timeframe,
            'from': start_ts,
            'to': min(end_ts, start_ts + self.config.max_candles_per_request * self._get_interval_seconds(timeframe)),
            'limit': self.config.max_candles_per_request,
        }
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_response(data)
                elif response.status_code == 429:
                    # Rate limit — صبر و تلاش مجدد
                    time.sleep(self.config.rate_limit_delay * 10)
                    continue
                else:
                    raise GateIODownloadError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise GateIODownloadError(f"Network error after retries: {e}")
                time.sleep(self.config.rate_limit_delay * (attempt + 1))
        
        return []
    
    def _parse_response(self, data: List) -> List[Dict[str, Any]]:
        """تبدیل پاسخ API به فرمت استاندارد"""
        candles = []
        
        for row in data:
            # Gate.io format: [timestamp, volume, close, high, low, open, ...]
            try:
                candle = {
                    'timestamp': int(row[0]),
                    'open': float(row[5]),
                    'high': float(row[3]),
                    'low': float(row[4]),
                    'close': float(row[2]),
                    'volume': float(row[1]),
                }
                candles.append(candle)
            except (IndexError, ValueError, TypeError):
                continue
        
        return candles
    
    def _get_interval_seconds(self, timeframe: str) -> int:
        """تبدیل timeframe به ثانیه"""
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        if unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 24 * 3600
        elif unit == 'w':
            return value * 7 * 24 * 3600
        else:
            raise GateIODownloadError(f"Unsupported timeframe: {timeframe}")
