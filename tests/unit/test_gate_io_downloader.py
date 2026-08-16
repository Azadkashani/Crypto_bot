# FILE: tests/unit/test_gate_io_downloader.py

"""
تست‌های Gate.io Downloader — بدون نیاز به اتصال واقعی
"""

import pytest
import requests
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
from src.strategy.data.gate_io_downloader import (
    GateIODownloader, GateIODownloadConfig, GateIODownloadError
)


class TestGateIODownloader:
    """تست‌های Downloader"""
    
    def get_downloader(self) -> GateIODownloader:
        return GateIODownloader(GateIODownloadConfig(
            rate_limit_delay=0.0,
            max_retries=1,
        ))
    
    def test_interval_conversion(self):
        """تست تبدیل timeframe"""
        downloader = self.get_downloader()
        
        assert downloader._get_interval_seconds("1m") == 60
        assert downloader._get_interval_seconds("5m") == 300
        assert downloader._get_interval_seconds("1h") == 3600
        assert downloader._get_interval_seconds("4h") == 14400
        assert downloader._get_interval_seconds("1d") == 86400
    
    def test_invalid_timeframe(self):
        """تست timeframe نامعتبر"""
        downloader = self.get_downloader()
        
        with pytest.raises(GateIODownloadError):
            downloader._get_interval_seconds("1x")
        
        with pytest.raises(GateIODownloadError):
            downloader._get_interval_seconds("")
        
        with pytest.raises(GateIODownloadError):
            downloader._get_interval_seconds("abc")
    
    def test_parse_response(self):
        """تست تبدیل پاسخ معتبر"""
        downloader = self.get_downloader()
        
        # شبیه‌سازی پاسخ Gate.io Futures
        # [timestamp, volume, close, high, low, open]
        mock_response = [
            [1700000000, "100.5", "50000", "51000", "49000", "49500"],
            [1700003600, "101.2", "50100", "51100", "49100", "49600"],
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 2
        assert candles[0]['timestamp'] == 1700000000
        assert candles[0]['open'] == 49500.0
        assert candles[0]['high'] == 51000.0
        assert candles[0]['low'] == 49000.0
        assert candles[0]['close'] == 50000.0
        assert candles[0]['volume'] == 100.5
    
    def test_parse_empty_response(self):
        """تست پاسخ خالی"""
        downloader = self.get_downloader()
        candles = downloader._parse_response([])
        assert candles == []
    
    def test_parse_none_response(self):
        """تست پاسخ None"""
        downloader = self.get_downloader()
        candles = downloader._parse_response(None)
        assert candles == []
    
    def test_parse_invalid_response(self):
        """تست پاسخ نامعتبر"""
        downloader = self.get_downloader()
        candles = downloader._parse_response(["invalid"])
        assert candles == []
    
    def test_parse_partial_response(self):
        """تست پاسخ ناقص"""
        downloader = self.get_downloader()
        mock_response = [
            [1700000000, "100.5", "50000", "51000", "49000"],  # ناقص
            [1700003600, "101.2", "50100", "51100", "49100", "49600"],  # کامل
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 1  # فقط کامل
        assert candles[0]['timestamp'] == 1700003600
    
    def test_fetch_ohlcv_pagination(self):
        """تست pagination"""
        downloader = self.get_downloader()
        
        # Mock fetch_batch
        batch1 = [
            {'timestamp': 1000, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 10},
            {'timestamp': 4600, 'open': 100.5, 'high': 102, 'low': 100, 'close': 101, 'volume': 12},
        ]
        batch2 = [
            {'timestamp': 8200, 'open': 101, 'high': 103, 'low': 100.5, 'close': 102, 'volume': 15},
        ]
        
        downloader._fetch_batch = MagicMock(side_effect=[batch1, batch2, []])
        
        candles = downloader.fetch_ohlcv(
            symbol="BTC_USDT",
            timeframe="1h",
            start_timestamp=1000,
            end_timestamp=11800
        )
        
        assert len(candles) == 3
        assert candles[0]['timestamp'] == 1000
        assert candles[-1]['timestamp'] == 8200
    
    def test_fetch_ohlcv_deduplication(self):
        """تست حذف duplicate"""
        downloader = self.get_downloader()
        
        batch1 = [
            {'timestamp': 1000, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 10},
            {'timestamp': 4600, 'open': 100.5, 'high': 102, 'low': 100, 'close': 101, 'volume': 12},
        ]
        # batch2 شامل duplicate از batch1
        batch2 = [
            {'timestamp': 4600, 'open': 100.5, 'high': 102, 'low': 100, 'close': 101, 'volume': 12},
            {'timestamp': 8200, 'open': 101, 'high': 103, 'low': 100.5, 'close': 102, 'volume': 15},
        ]
        
        downloader._fetch_batch = MagicMock(side_effect=[batch1, batch2, []])
        
        candles = downloader.fetch_ohlcv(
            symbol="BTC_USDT",
            timeframe="1h",
            start_timestamp=1000,
            end_timestamp=11800
        )
        
        assert len(candles) == 3  # نه 4
        assert len(set(c['timestamp'] for c in candles)) == 3
    
    def test_fetch_http_error(self):
        """تست خطای HTTP"""
        downloader = self.get_downloader()
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        downloader.session.get = MagicMock(return_value=mock_response)
        
        with pytest.raises(GateIODownloadError):
            downloader._fetch_batch(
                symbol="BTC_USDT",
                timeframe="1h",
                start_ts=1000,
                end_ts=2000
            )
    
    def test_fetch_timeout(self):
        """تست timeout"""
        downloader = self.get_downloader()
        
        downloader.session.get = MagicMock(
            side_effect=requests.exceptions.Timeout("timeout")
        )
        
        with pytest.raises(GateIODownloadError):
            downloader._fetch_batch(
                symbol="BTC_USDT",
                timeframe="1h",
                start_ts=1000,
                end_ts=2000
            )