# FILE: tests/unit/test_strategy_validator.py

"""
تست‌های Strategy Validator
"""

import pytest
from typing import List, Dict, Any
from src.strategy.validation.strategy_validator import StrategyValidator
from src.strategy.validation.validation_types import (
    ValidationConfig, EdgeAssessment, SampleSize
)


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


class TestStrategyValidator:
    """تست‌های Validator"""
    
    def get_validator(self) -> StrategyValidator:
        return StrategyValidator(ValidationConfig(
            min_trades_for_assessment=30,
            min_trades_for_sufficiency=100,
            symbol="BTC_USDT",
            timeframe="1h",
            initial_equity=10000.0
        ))
    
    def test_validation_empty_data(self):
        """تست داده خالی"""
        validator = self.get_validator()
        
        with pytest.raises(Exception):
            validator.validate([])
    
    def test_validation_valid_data(self):
        """تست داده معتبر"""
        validator = self.get_validator()
        data = create_valid_ohlcv(100)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report is not None
        assert report.dataset_info.row_count == 100
        assert report.dataset_info.symbol == "BTC_USDT"
    
    def test_validation_report_structure(self):
        """تست ساختار گزارش"""
        validator = self.get_validator()
        data = create_valid_ohlcv(50)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.performance is not None
        assert report.long_short is not None
        assert report.edge_assessment in [
            EdgeAssessment.STRONG, EdgeAssessment.PROMISING,
            EdgeAssessment.INCONCLUSIVE, EdgeAssessment.NEGATIVE
        ]
        assert report.sample_size in [
            SampleSize.SUFFICIENT, SampleSize.PRELIMINARY,
            SampleSize.INSUFFICIENT
        ]
    
    def test_validation_lookahead_test(self):
        """تست Look-ahead در Validator"""
        validator = self.get_validator()
        data = create_valid_ohlcv(80)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.lookahead_test == "PASS"
    
    def test_validation_determinism_test(self):
        """تست قطعیت در Validator"""
        validator = self.get_validator()
        data = create_valid_ohlcv(60)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.determinism_test == "PASS"
    
    def test_validation_future_mutation_test(self):
        """تست Future Mutation در Validator"""
        validator = self.get_validator()
        data = create_valid_ohlcv(60)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.future_mutation_test == "PASS"
    
    def test_validation_truncated_data_test(self):
        """تست Truncated Data در Validator"""
        validator = self.get_validator()
        data = create_valid_ohlcv(60)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.truncated_data_test == "PASS"
    
    def test_validation_insufficient_sample(self):
        """تست حجم نمونه ناکافی"""
        validator = self.get_validator()
        data = create_valid_ohlcv(30)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        
        assert report.sample_size == SampleSize.INSUFFICIENT
        assert len(report.warnings) > 0
    
    def test_validation_text_report(self):
        """تست تولید گزارش متنی"""
        validator = self.get_validator()
        data = create_valid_ohlcv(50)
        
        report = validator.validate(data, "BTC_USDT", "1h")
        text = report.generate_text_report()
        
        assert "FTR STRATEGY VALIDATION REPORT" in text
        assert "SYMBOL" in text
        assert "TIMEFRAME" in text
