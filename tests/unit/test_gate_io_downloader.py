# FILE: tests/unit/test_gate_io_downloader.py

"""
تست‌های Gate.io Downloader
"""

import pytest
from typing import List, Dict, Any
from src.strategy.data.gate_io_downloader import (
    GateIODownloader, GateIODownloadConfig, GateIODownloadError
)


class TestGateIODownloader:
    """تست‌های Downloader"""
    
    def test_interval_conversion(self):
        """تست تبدیل timeframe به ثانیه"""
        downloader = GateIODownloader()
        
        assert downloader._get_interval_seconds("1m") == 60
        assert downloader._get_interval_seconds("5m") == 300
        assert downloader._get_interval_seconds("1h") == 3600
        assert downloader._get_interval_seconds("4h") == 14400
        assert downloader._get_interval_seconds("1d") == 86400
    
    def test_invalid_timeframe(self):
        """تست timeframe نامعتبر"""
        downloader = GateIODownloader()
        
        with pytest.raises(GateIODownloadError):
            downloader._get_interval_seconds("1x")
    
    def test_parse_response(self):
        """تست تبدیل پاسخ API"""
        downloader = GateIODownloader()
        
        # شبیه‌سازی پاسخ Gate.io
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
        downloader = GateIODownloader()
        
        candles = downloader._parse_response([])
        
        assert candles == []
    
    def test_parse_invalid_response(self):
        """تست پاسخ نامعتبر"""
        downloader = GateIODownloader()
        
        candles = downloader._parse_response(["invalid"])
        
        assert candles == []
