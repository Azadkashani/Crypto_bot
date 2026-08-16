# FILE: src/strategy/data/gate_io_downloader.py

"""
Gate.io Historical Data Downloader — USDT-M Perpetual Futures
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
    rate_limit_delay: float = 0.15
    max_candles_per_request: int = 2000
    timeout: int = 30
    max_retries: int = 5


class GateIODownloader:
    """
    دانلود داده تاریخی OHLCV از Gate.io USDT-M Perpetual Futures
    """
    
    def __init__(self, config: Optional[GateIODownloadConfig] = None):
        self.config = config or GateIODownloadConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
    
    def fetch_ohlcv(
        self,
        symbol: str = "BTC_USDT",
        timeframe: str = "1h",
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        دریافت کندل‌های OHLCV از Gate.io Futures
        """
        all_candles = []
        
        if end_timestamp is None:
            end_timestamp = int(time.time())
        
        if start_timestamp is None:
            start_timestamp = end_timestamp - (180 * 24 * 3600)
        
        interval_seconds = self._get_interval_seconds(timeframe)
        window_seconds = self.config.max_candles_per_request * interval_seconds
        
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            current_end = min(current_start + window_seconds, end_timestamp)
            
            batch = self._fetch_batch(
                symbol=symbol,
                timeframe=timeframe,
                start_ts=current_start,
                end_ts=current_end
            )
            
            if batch:
                all_candles.extend(batch)
                last_ts = batch[-1]['timestamp']
                current_start = last_ts + interval_seconds
            else:
                current_start = current_end
            
            if current_start >= current_end:
                break
            
            time.sleep(self.config.rate_limit_delay)
        
        # حذف duplicate
        seen = set()
        unique_candles = []
        
        for candle in all_candles:
            ts = candle['timestamp']
            if ts not in seen:
                seen.add(ts)
                unique_candles.append(candle)
        
        unique_candles.sort(key=lambda c: c['timestamp'])
        
        return unique_candles
    
    def _fetch_batch(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> List[Dict[str, Any]]:
        """دریافت یک batch"""
        url = f"{self.config.base_url}/{self.config.api_version}/futures/usdt/candlesticks"
        
        params = {
            'contract': symbol,
            'interval': timeframe,
            'from': start_ts,
            'to': end_ts,
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
                    wait = self.config.rate_limit_delay * 10 * (attempt + 1)
                    time.sleep(wait)
                    continue
                elif response.status_code >= 500:
                    time.sleep(self.config.rate_limit_delay * (attempt + 1))
                    continue
                else:
                    raise GateIODownloadError(
                        f"HTTP {response.status_code}: {response.text[:300]}"
                    )
            except requests.Timeout:
                if attempt == self.config.max_retries - 1:
                    raise GateIODownloadError("Timeout after retries")
                time.sleep(self.config.rate_limit_delay * (attempt + 1))
            except requests.ConnectionError:
                if attempt == self.config.max_retries - 1:
                    raise GateIODownloadError("Connection error after retries")
                time.sleep(self.config.rate_limit_delay * (attempt + 1))
            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise GateIODownloadError(f"Request error: {e}")
                time.sleep(self.config.rate_limit_delay * (attempt + 1))
        
        return []
    
    def _parse_response(self, data: Any) -> List[Dict[str, Any]]:
        """
        تبدیل پاسخ Gate.io Futures به فرمت استاندارد
        
        Gate.io Futures v4 response format:
        [
            {"t": 1700000000, "v": 100500, "c": "50000", "h": "51000", "l": "49000", "o": "49500"},
            ...
        ]
        
        یا ممکن است به صورت list of lists برگردد:
        [[timestamp, volume, close, high, low, open], ...]
        """
        if not isinstance(data, list):
            return []
        
        candles = []
        
        for row in data:
            candle = self._parse_row(row)
            if candle is not None:
                candles.append(candle)
        
        return candles
    
    def _parse_row(self, row: Any) -> Optional[Dict[str, Any]]:
        """پارس یک کندل از پاسخ API"""
        try:
            # فرمت dict: {"t": ..., "v": ..., "c": ..., "h": ..., "l": ..., "o": ...}
            if isinstance(row, dict):
                timestamp = int(row.get('t', 0))
                volume = float(row.get('v', 0))
                close = float(row.get('c', 0))
                high = float(row.get('h', 0))
                low = float(row.get('l', 0))
                open_price = float(row.get('o', 0))
            
            # فرمت list: [timestamp, volume, close, high, low, open]
            elif isinstance(row, list) and len(row) >= 6:
                timestamp = int(row[0])
                volume = float(row[1])
                close = float(row[2])
                high = float(row[3])
                low = float(row[4])
                open_price = float(row[5])
            
            else:
                return None
            
            if timestamp <= 0:
                return None
            
            candle = {
                'timestamp': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
            }
            
            # بررسی اعتبار
            if candle['high'] < candle['low']:
                return None
            if candle['open'] <= 0 or candle['close'] <= 0:
                return None
            
            return candle
        
        except (ValueError, TypeError, KeyError):
            return None
    
    def _get_interval_seconds(self, timeframe: str) -> int:
        """تبدیل timeframe به ثانیه"""
        if not timeframe or len(timeframe) < 2:
            raise GateIODownloadError(f"Invalid timeframe: {timeframe}")
        
        unit = timeframe[-1]
        
        try:
            value = int(timeframe[:-1])
        except ValueError:
            raise GateIODownloadError(f"Invalid timeframe: {timeframe}")
        
        if value <= 0:
            raise GateIODownloadError(f"Invalid timeframe value: {timeframe}")
        
        if unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 24 * 3600
        elif unit == 'w':
            return value * 7 * 24 * 3600
        else:
            raise GateIODownloadError(f"Unsupported timeframe unit: {unit}")
