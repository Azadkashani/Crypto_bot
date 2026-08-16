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
            max_candles_per_request=100,
        ))
    
    def test_no_limit_param_with_from_to(self):
        """تست عدم وجود limit در پارامترها"""
        downloader = self.get_downloader()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=[])
        
        downloader.session.get = MagicMock(return_value=mock_response)
        
        downloader._fetch_batch(
            symbol="BTC_USDT",
            timeframe="1h",
            start_ts=1000,
            end_ts=2000
        )
        
        call_kwargs = downloader.session.get.call_args
        params = call_kwargs[1].get('params', {})
        
        assert 'limit' not in params
        assert 'from' in params
        assert 'to' in params
    
    def test_parse_dict_response(self):
        """تست پارس پاسخ dict (Gate.io v4 format)"""
        downloader = self.get_downloader()
        
        mock_response = [
            {"t": 1700000000, "v": 100500, "c": "50000", "h": "51000", "l": "49000", "o": "49500"},
            {"t": 1700003600, "v": 101200, "c": "50100", "h": "51100", "l": "49100", "o": "49600"},
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 2
        assert candles[0]['timestamp'] == 1700000000
        assert candles[0]['open'] == 49500.0
        assert candles[0]['high'] == 51000.0
        assert candles[0]['low'] == 49000.0
        assert candles[0]['close'] == 50000.0
        assert candles[0]['volume'] == 100500.0
    
    def test_parse_list_response(self):
        """تست پارس پاسخ list (فرمت قدیمی)"""
        downloader = self.get_downloader()
        
        mock_response = [
            [1700000000, "100.5", "50000", "51000", "49000", "49500"],
            [1700003600, "101.2", "50100", "51100", "49100", "49600"],
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 2
        assert candles[0]['open'] == 49500.0
    
    def test_parse_mixed_response(self):
        """تست پارس پاسخ ترکیبی"""
        downloader = self.get_downloader()
        
        mock_response = [
            {"t": 1700000000, "v": 100, "c": "500", "h": "510", "l": "490", "o": "495"},
            [1700003600, "101", "501", "511", "491", "496"],
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 2
    
    def test_parse_invalid_row_skipped(self):
        """تست پارس ردیف نامعتبر"""
        downloader = self.get_downloader()
        
        mock_response = [
            {"t": 1700000000, "v": 100, "c": "500", "h": "510", "l": "490", "o": "495"},
            "invalid",
            None,
            {"t": 1700003600, "v": 101, "c": "501", "h": "511", "l": "491", "o": "496"},
        ]
        
        candles = downloader._parse_response(mock_response)
        
        assert len(candles) == 2
    
    def test_parse_empty_response(self):
        """تست پاسخ خالی"""
        downloader = self.get_downloader()
        candles = downloader._parse_response([])
        assert candles == []
    
    def test_interval_conversion(self):
        """تست تبدیل timeframe"""
        downloader = self.get_downloader()
        assert downloader._get_interval_seconds("1h") == 3600
        assert downloader._get_interval_seconds("5m") == 300
    
    def test_fetch_ohlcv_pagination(self):
        """تست pagination"""
        downloader = self.get_downloader()
        
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
    
    def test_http_error_no_retry(self):
        """تست خطای 400"""
        downloader = self.get_downloader()
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "INVALID_PARAM_VALUE"
        
        downloader.session.get = MagicMock(return_value=mock_response)
        
        with pytest.raises(GateIODownloadError):
            downloader._fetch_batch(
                symbol="BTC_USDT", timeframe="1h", start_ts=1000, end_ts=2000
            )
    
    def test_timeout_error(self):
        """تست timeout"""
        downloader = self.get_downloader()
        
        downloader.session.get = MagicMock(
            side_effect=requests.exceptions.Timeout("timeout")
        )
        
        with pytest.raises(GateIODownloadError):
            downloader._fetch_batch(
                symbol="BTC_USDT", timeframe="1h", start_ts=1000, end_ts=2000
            )
