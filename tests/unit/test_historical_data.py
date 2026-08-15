# FILE: tests/unit/test_historical_data.py

"""
تست‌های Historical Data Loader
"""

import pytest
import csv
import os
import tempfile
from typing import List, Dict, Any
from src.strategy.data.data_types import DataValidationResult
from src.strategy.data.data_validator import OHLCVDataValidator
from src.strategy.data.historical_data_loader import HistoricalDataLoader


def create_valid_ohlcv(n: int = 100) -> List[Dict[str, Any]]:
    """ایجاد داده OHLCV معتبر"""
    data = []
    for i in range(n):
        price = 100 + i * 0.5
        data.append({
            'timestamp': i * 3600,
            'open': price - 0.2,
            'high': price + 0.5,
            'low': price - 0.5,
            'close': price,
            'volume': 100.0,
        })
    return data


def create_csv_file(data: List[Dict[str, Any]]) -> str:
    """ایجاد فایل CSV موقت"""
    tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
    fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    writer = csv.DictWriter(tmp, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    tmp.close()
    return tmp.name


class TestDataValidator:
    """تست‌های Validator"""
    
    def setup_method(self):
        self.validator = OHLCVDataValidator()
    
    def test_valid_candles(self):
        """تست کندل‌های معتبر"""
        data = create_valid_ohlcv(50)
        result = self.validator.validate_candles(data)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_empty_dataset(self):
        """تست داده خالی"""
        result = self.validator.validate_candles([])
        
        assert not result.is_valid
        assert "Empty dataset" in result.errors
    
    def test_missing_field(self):
        """تست فیلد ناقص"""
        data = create_valid_ohlcv(10)
        del data[5]['volume']
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
        assert any("missing field" in e for e in result.errors)
    
    def test_negative_price(self):
        """تست قیمت منفی"""
        data = create_valid_ohlcv(10)
        data[3]['close'] = -50.0
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
    
    def test_invalid_ohlc(self):
        """تست OHLC نامعتبر"""
        data = create_valid_ohlcv(10)
        data[2]['high'] = 50.0  # high < low
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
    
    def test_duplicate_timestamp(self):
        """تست timestamp تکراری"""
        data = create_valid_ohlcv(10)
        data[5]['timestamp'] = data[4]['timestamp']
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
        assert result.duplicate_count > 0
    
    def test_unsorted_timestamp(self):
        """تست timestamp نامرتب"""
        data = create_valid_ohlcv(10)
        data[3]['timestamp'] = data[8]['timestamp'] + 100
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
    
    def test_negative_volume(self):
        """تست حجم منفی"""
        data = create_valid_ohlcv(10)
        data[4]['volume'] = -10.0
        
        result = self.validator.validate_candles(data)
        
        assert not result.is_valid
    
    def test_gap_detection(self):
        """تست تشخیص gap"""
        data = create_valid_ohlcv(20)
        # ایجاد gap: کندل 10 تا 11 فاصله 2 برابر
        for i in range(10, 20):
            data[i]['timestamp'] += 3600
        
        result = self.validator.validate_candles(
            data,
            expected_interval_seconds=3600
        )
        
        assert result.gap_count > 0
        assert len(result.gap_details) > 0


class TestHistoricalDataLoader:
    """تست‌های Loader"""
    
    def setup_method(self):
        self.loader = HistoricalDataLoader()
    
    def test_load_valid_csv(self):
        """تست بارگذاری CSV معتبر"""
        data = create_valid_ohlcv(50)
        csv_path = create_csv_file(data)
        
        try:
            candles, info, validation = self.loader.load_csv(
                csv_path, symbol="BTC_USDT", timeframe="1h"
            )
            
            assert len(candles) == 50
            assert validation.is_valid
            assert info.symbol == "BTC_USDT"
            assert info.row_count == 50
        finally:
            os.unlink(csv_path)
    
    def test_load_missing_file(self):
        """تست فایل ناموجود"""
        with pytest.raises(FileNotFoundError):
            self.loader.load_csv("/nonexistent/file.csv")
    
    def test_load_missing_column(self):
        """تست CSV با ستون ناقص"""
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        tmp.write("timestamp,open,high,low,close\n")
        tmp.write("0,100,101,99,100\n")
        tmp.close()
        
        try:
            with pytest.raises(ValueError):
                self.loader.load_csv(tmp.name)
        finally:
            os.unlink(tmp.name)
    
    def test_save_and_reload(self):
        """تست ذخیره و بارگذاری مجدد"""
        data = create_valid_ohlcv(30)
        tmp_dir = tempfile.mkdtemp()
        csv_path = os.path.join(tmp_dir, "test.csv")
        
        try:
            self.loader.save_csv(data, csv_path)
            
            candles, info, validation = self.loader.load_csv(
                csv_path, symbol="TEST_USDT", timeframe="1h"
            )
            
            assert len(candles) == 30
            assert info.row_count == 30
            assert validation.is_valid
        finally:
            os.unlink(csv_path)
            os.rmdir(tmp_dir)
    
    def test_save_metadata(self):
        """تست ذخیره metadata"""
        tmp_dir = tempfile.mkdtemp()
        meta_path = os.path.join(tmp_dir, "test.json")
        
        from src.strategy.data.data_types import DatasetInfo
        
        info = DatasetInfo(
            symbol="BTC_USDT",
            timeframe="1h",
            source="TEST",
            start_timestamp=0,
            end_timestamp=3600,
            row_count=2,
            timezone="UTC"
        )
        
        try:
            self.loader.save_metadata(info, meta_path)
            
            loaded = self.loader.load_metadata(meta_path)
            
            assert loaded.symbol == "BTC_USDT"
            assert loaded.timeframe == "1h"
            assert loaded.row_count == 2
        finally:
            os.unlink(meta_path)
            os.rmdir(tmp_dir)
    
    def test_checksum(self):
        """تست محاسبه checksum"""
        data = create_valid_ohlcv(20)
        csv_path = create_csv_file(data)
        
        try:
            checksum = self.loader._calculate_checksum(csv_path)
            
            assert len(checksum) == 64
            assert all(c in '0123456789abcdef' for c in checksum)
        finally:
            os.unlink(csv_path)
    
    def test_deterministic_reload(self):
        """تست بارگذاری مجدد قطعی"""
        data = create_valid_ohluv(40)
        csv_path = create_csv_file(data)
        
        try:
            candles1, info1, val1 = self.loader.load_csv(csv_path)
            candles2, info2, val2 = self.loader.load_csv(csv_path)
            
            assert info1.checksum == info2.checksum
            assert len(candles1) == len(candles2)
            assert candles1[0]['timestamp'] == candles2[0]['timestamp']
            assert candles1[-1]['close'] == candles2[-1]['close']
        finally:
            os.unlink(csv_path)
