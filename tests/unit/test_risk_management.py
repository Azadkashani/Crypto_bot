# FILE: tests/unit/test_risk_management.py

"""
تست‌های Risk Management Layer
"""

import pytest
from typing import Optional
from src.strategy.trade.trade_signal_types import TradeSignal
from src.strategy.risk.risk_management_engine import RiskManagementEngine
from src.strategy.risk.risk_types import (
    RiskConfig, RiskAssessment, RiskRejectionReason
)


def create_long_trade_signal() -> TradeSignal:
    """ایجاد TradeSignal صعودی معتبر"""
    return TradeSignal(
        signal_id="TS_LONG_1",
        symbol="BTC_USDT",
        timeframe="1h",
        direction="LONG",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=106.0,
        risk_reward=3.0,  # (106-100)/(100-98) = 6/2 = 3.0
        signal_quality_score=85.0,
        signal_quality_classification="QUALIFIED",
        zone_id="zone_1",
        created_timestamp=100000,
        is_valid=True
    )


def create_short_trade_signal() -> TradeSignal:
    """ایجاد TradeSignal نزولی معتبر"""
    return TradeSignal(
        signal_id="TS_SHORT_1",
        symbol="BTC_USDT",
        timeframe="1h",
        direction="SHORT",
        entry_price=100.0,
        stop_loss=102.0,
        take_profit=94.0,
        risk_reward=3.0,  # (100-94)/(102-100) = 6/2 = 3.0
        signal_quality_score=85.0,
        signal_quality_classification="QUALIFIED",
        zone_id="zone_2",
        created_timestamp=100000,
        is_valid=True
    )


def get_default_config() -> RiskConfig:
    """پیکربندی پیش‌فرض"""
    return RiskConfig(
        risk_per_trade_pct=1.0,
        max_risk_per_trade_pct=5.0,
        min_risk_reward=0.0,
        max_position_notional=None
    )


class TestRiskManagement:
    """تست‌های Risk Management"""
    
    def test_long_position_size(self):
        """تست محاسبه اندازه پوزیشن LONG"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0,
            risk_per_trade_pct=1.0
        )
        
        assert assessment.is_valid
        assert assessment.risk_amount == 100.0  # 10000 * 1%
        assert assessment.price_risk == 2.0  # 100 - 98
        assert assessment.position_size == 50.0  # 100 / 2
        assert assessment.notional_value == 5000.0  # 50 * 100
    
    def test_short_position_size(self):
        """تست محاسبه اندازه پوزیشن SHORT"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_short_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0,
            risk_per_trade_pct=1.0
        )
        
        assert assessment.is_valid
        assert assessment.risk_amount == 100.0
        assert assessment.price_risk == 2.0  # 102 - 100
        assert assessment.position_size == 50.0
        assert assessment.notional_value == 5000.0
    
    def test_zero_stop_distance(self):
        """تست فاصله توقف صفر"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        signal.stop_loss = signal.entry_price  # SL = Entry
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_STOP_DISTANCE in assessment.rejection_reasons
    
    def test_negative_equity(self):
        """تست equity منفی"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=-1000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_EQUITY in assessment.rejection_reasons
    
    def test_zero_risk_percent(self):
        """تست ریسک صفر درصد"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0,
            risk_per_trade_pct=0.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_RISK_PERCENT in assessment.rejection_reasons
    
    def test_excessive_risk(self):
        """تست ریسک بیش از حد"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0,
            risk_per_trade_pct=10.0  # > max 5%
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.RISK_LIMIT_EXCEEDED in assessment.rejection_reasons
    
    def test_rr_below_minimum(self):
        """تست R:R کمتر از حداقل"""
        config = RiskConfig(
            risk_per_trade_pct=1.0,
            max_risk_per_trade_pct=5.0,
            min_risk_reward=2.0  # حداقل R:R
        )
        engine = RiskManagementEngine(config)
        
        signal = create_long_trade_signal()
        signal.take_profit = 101.0  # R:R = (101-100)/(100-98) = 1/2 = 0.5
        signal.risk_reward = 0.5
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.RR_BELOW_MINIMUM in assessment.rejection_reasons
    
    def test_long_invalid_geometry(self):
        """تست هندسه نامعتبر LONG"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        signal.stop_loss = 105.0  # SL > Entry — نامعتبر
        signal.is_valid = False
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_TRADE_SIGNAL in assessment.rejection_reasons
    
    def test_short_invalid_geometry(self):
        """تست هندسه نامعتبر SHORT"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_short_trade_signal()
        signal.stop_loss = 95.0  # SL < Entry — نامعتبر
        signal.is_valid = False
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_TRADE_SIGNAL in assessment.rejection_reasons
    
    def test_notional_calculation(self):
        """تست محاسبه Notional"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=20000.0,
            risk_per_trade_pct=1.0
        )
        
        # Equity=20000, Risk=200, Price Risk=2, Size=100
        # Notional = 100 * 100 = 10000
        assert assessment.is_valid
        assert assessment.risk_amount == 200.0
        assert assessment.position_size == 100.0
        assert assessment.notional_value == 10000.0
    
    def test_risk_independent_of_leverage(self):
        """تست استقلال ریسک از اهرم"""
        # Risk Layer اصلاً leverage ندارد
        # ریسک فقط از equity و risk percent محاسبه می‌شود
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment = engine.calculate_position_size(
            signal,
            account_equity=10000.0,
            risk_per_trade_pct=1.0
        )
        
        assert assessment.risk_amount == 100.0
        # بدون توجه به leverage
        # در آینده leverage در Execution Layer اعمال می‌شود
    
    def test_determinism(self):
        """تست قطعیت"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        assessment1 = engine.calculate_position_size(
            signal, account_equity=10000.0, risk_per_trade_pct=1.0
        )
        engine.reset()
        assessment2 = engine.calculate_position_size(
            signal, account_equity=10000.0, risk_per_trade_pct=1.0
        )
        
        assert assessment1.position_size == assessment2.position_size
        assert assessment1.risk_amount == assessment2.risk_amount
        assert assessment1.notional_value == assessment2.notional_value
        assert assessment1.is_valid == assessment2.is_valid
    
    def test_no_lookahead(self):
        """تست عدم Look-ahead"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        
        # Risk فقط از TradeSignal و equity استفاده می‌کند
        # هیچ داده آینده‌ای وارد نمی‌شود
        assessment = engine.calculate_position_size(
            signal, account_equity=10000.0
        )
        
        assert assessment.is_valid
        assert assessment.timestamp == signal.created_timestamp
    
    def test_qualified_signal_valid(self):
        """تست سیگنال QUALIFIED معتبر"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        signal.signal_quality_classification = "QUALIFIED"
        
        assessment = engine.calculate_position_size(
            signal, account_equity=10000.0
        )
        
        assert assessment.is_valid
    
    def test_invalid_trade_signal_rejected(self):
        """تست سیگنال نامعتبر"""
        engine = RiskManagementEngine(get_default_config())
        signal = create_long_trade_signal()
        signal.is_valid = False
        signal.validation_errors = ["Invalid direction"]
        
        assessment = engine.calculate_position_size(
            signal, account_equity=10000.0
        )
        
        assert not assessment.is_valid
        assert RiskRejectionReason.INVALID_TRADE_SIGNAL in assessment.rejection_reasons
