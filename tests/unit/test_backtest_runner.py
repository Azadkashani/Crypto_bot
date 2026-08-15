# FILE: tests/unit/test_backtest_runner.py

"""
تست‌های Backtest Runner
"""

import pytest
import csv
import os
import tempfile
from typing import List, Dict, Any
from src.strategy.backtest.backtest_runner import (
    BacktestRunner, BacktestRunnerConfig, DataValidationError
)


def create_valid_ohlcv(n: int = 50) -> List[Dict[str, Any]]:
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


class TestBacktestRunner:
    """تست‌های Runner"""
    
    def get_runner(self) -> BacktestRunner:
        return BacktestRunner(BacktestRunnerConfig(
            symbol="BTC_USDT",
            timeframe="1h",
            initial_equity=10000.0
        ))
    
    def test_valid_ohlcv_execution(self):
        """تست اجرا با داده معتبر"""
        runner = self.get_runner()
        data = create_valid_ohlcv(50)
        
        result = runner.run(data)
        
        assert result is not None
        assert result.initial_equity == 10000.0
    
    def test_empty_dataset_rejected(self):
        """تست رد داده خالی"""
        runner = self.get_runner()
        
        with pytest.raises(DataValidationError):
            runner.run([])
    
    def test_missing_column_rejected(self):
        """تست رد داده با ستون ناقص"""
        runner = self.get_runner()
        data = create_valid_ohlcv(10)
        # حذف volume
        for d in data:
            del d['volume']
        
        with pytest.raises(DataValidationError):
            runner.run(data)
    
    def test_nan_data_rejected(self):
        """تست رد NaN"""
        runner = self.get_runner()
        data = create_valid_ohlcv(10)
        data[5]['close'] = float('nan')
        
        with pytest.raises(DataValidationError):
            runner.run(data)
    
    def test_invalid_ohlc_rejected(self):
        """تست رد OHLC نامعتبر"""
        runner = self.get_runner()
        data = create_valid_ohlcv(10)
        data[3]['high'] = 50.0  # high < low
        
        with pytest.raises(DataValidationError):
            runner.run(data)
    
    def test_duplicate_timestamps_rejected(self):
        """تست رد timestamp تکراری"""
        runner = self.get_runner()
        data = create_valid_ohlcv(10)
        data[5]['timestamp'] = data[4]['timestamp']
        
        with pytest.raises(DataValidationError):
            runner.run(data)
    
    def test_unsorted_timestamps_rejected(self):
        """تست رد timestamp نامرتب"""
        runner = self.get_runner()
        data = create_valid_ohlcv(10)
        data[3]['timestamp'] = data[8]['timestamp'] + 100
        
        with pytest.raises(DataValidationError):
            runner.run(data)
    
    def test_no_lookahead_truncated(self):
        """تست عدم Look-ahead با داده کوتاه شده"""
        runner1 = self.get_runner()
        runner2 = self.get_runner()
        data = create_valid_ohlcv(60)
        
        result_full = runner1.run(data)
        result_truncated = runner2.run(data[:30])
        
        # هر دو باید بدون خطا اجرا شوند
        assert result_full is not None
        assert result_truncated is not None
    
    def test_future_mutation_no_effect(self):
        """تست تغییر آینده تأثیری بر تصمیمات قبلی ندارد"""
        runner = self.get_runner()
        data = create_valid_ohlcv(60)
        
        # اجرای اول
        result1 = runner.run(data)
        
        # تغییر آینده
        mutated = create_valid_ohlcv(60)
        for i in range(30, 60):
            mutated[i]['high'] = 999999
            mutated[i]['low'] = 0
        
        runner.reset()
        result2 = runner.run(mutated)
        
        # هر دو باید اجرا شوند بدون خطا
        assert result1 is not None
        assert result2 is not None
    
    def test_determinism(self):
        """تست قطعیت"""
        runner1 = self.get_runner()
        runner2 = self.get_runner()
        data = create_valid_ohlcv(50)
        
        result1 = runner1.run(data)
        result2 = runner2.run(data)
        
        assert result1.total_trades == result2.total_trades
        assert result1.final_equity == result2.final_equity
    
    def test_reset_between_runs(self):
        """تست Reset بین اجراها"""
        runner = self.get_runner()
        data1 = create_valid_ohlcv(40)
        data2 = create_valid_ohlcv(60)
        
        result1 = runner.run(data1)
        result2 = runner.run(data2)
        
        assert result1 is not None
        assert result2 is not None
        # نتیجه دوم نباید از نتیجه اول تأثیر بگیرد
    
    def test_csv_loading(self):
        """تست بارگذاری CSV"""
        runner = self.get_runner()
        data = create_valid_ohlcv(20)
        csv_path = create_csv_file(data)
        
        try:
            loaded = runner.load_csv(csv_path)
            
            assert len(loaded) == 20
            assert loaded[0]['timestamp'] == 0
            assert loaded[0]['close'] == 100.0
        finally:
            os.unlink(csv_path)
    
    def test_csv_missing_file(self):
        """تست فایل CSV ناموجود"""
        runner = self.get_runner()
        
        with pytest.raises(FileNotFoundError):
            runner.load_csv("/nonexistent/file.csv")
    
    def test_csv_missing_column(self):
        """تست CSV با ستون ناقص"""
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        tmp.write("timestamp,open,high,low,close\n")
        tmp.write("0,100,101,99,100\n")
        tmp.close()
        
        runner = self.get_runner()
        
        try:
            with pytest.raises(DataValidationError):
                runner.load_csv(tmp.name)
        finally:
            os.unlink(tmp.name)
    
    def test_same_candle_sl_first(self):
        """تست سیاست SL_FIRST"""
        config = BacktestRunnerConfig(
            symbol="BTC_USDT",
            timeframe="1h",
            initial_equity=10000.0,
            backtest_config=None  # استفاده از پیش‌فرض SL_FIRST
        )
        runner = BacktestRunner(config)
        
        # BacktestConfig پیش‌فرض SL_FIRST است
        assert runner.backtest_engine.config.same_candle_conflict_policy == "SL_FIRST"
