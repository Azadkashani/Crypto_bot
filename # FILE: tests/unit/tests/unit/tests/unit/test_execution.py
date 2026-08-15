# FILE: tests/unit/test_execution.py

"""
تست‌های Execution Layer
"""

import pytest
from typing import Optional
from src.strategy.risk.risk_types import (
    RiskAssessment, RiskRejectionReason
)
from src.strategy.execution.execution_engine import (
    ExecutionEngine, ExecutionConfig, ExecutionMode
)
from src.strategy.execution.execution_types import (
    OrderType, OrderStatus
)


def create_long_risk_assessment() -> RiskAssessment:
    """ایجاد Risk Assessment صعودی معتبر"""
    return RiskAssessment(
        assessment_id="RA_LONG_1",
        signal_id="TS_LONG_1",
        symbol="BTC_USDT",
        direction="LONG",
        account_equity=10000.0,
        risk_per_trade_pct=1.0,
        risk_amount=100.0,
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=106.0,
        price_risk=2.0,
        position_size=50.0,
        notional_value=5000.0,
        risk_reward=3.0,
        is_valid=True,
        rejection_reasons=[],
        timestamp=100000,
        metadata={
            'zone_id': 'zone_1',
            'signal_quality_score': 85.0,
            'signal_quality_classification': 'QUALIFIED',
        }
    )


def create_short_risk_assessment() -> RiskAssessment:
    """ایجاد Risk Assessment نزولی معتبر"""
    return RiskAssessment(
        assessment_id="RA_SHORT_1",
        signal_id="TS_SHORT_1",
        symbol="BTC_USDT",
        direction="SHORT",
        account_equity=10000.0,
        risk_per_trade_pct=1.0,
        risk_amount=100.0,
        entry_price=100.0,
        stop_loss=102.0,
        take_profit=94.0,
        price_risk=2.0,
        position_size=50.0,
        notional_value=5000.0,
        risk_reward=3.0,
        is_valid=True,
        rejection_reasons=[],
        timestamp=100000,
        metadata={
            'zone_id': 'zone_2',
            'signal_quality_score': 85.0,
            'signal_quality_classification': 'QUALIFIED',
        }
    )


class TestExecution:
    """تست‌های Execution Layer"""
    
    def get_engine(self) -> ExecutionEngine:
        return ExecutionEngine(ExecutionConfig(
            mode=ExecutionMode.DRY_RUN,
            order_type=OrderType.LIMIT,
            risk_consistency_tolerance_pct=1.0
        ))
    
    def test_valid_long_order(self):
        """تست سفارش معتبر LONG"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        
        result = engine.create_order(ra)
        
        assert result.success
        assert result.order is not None
        assert result.order.direction == "LONG"
        assert result.order.entry_price == 100.0
        assert result.order.stop_loss == 98.0
        assert result.order.take_profit == 106.0
        assert result.order.quantity == 50.0
        assert result.order.status == OrderStatus.VALIDATED
    
    def test_valid_short_order(self):
        """تست سفارش معتبر SHORT"""
        engine = self.get_engine()
        ra = create_short_risk_assessment()
        
        result = engine.create_order(ra)
        
        assert result.success
        assert result.order is not None
        assert result.order.direction == "SHORT"
        assert result.order.stop_loss == 102.0
        assert result.order.take_profit == 94.0
    
    def test_zero_entry_rejected(self):
        """تست Entry صفر"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.entry_price = 0.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
        assert len(result.errors) > 0
    
    def test_negative_entry_rejected(self):
        """تست Entry منفی"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.entry_price = -100.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_long_invalid_sl(self):
        """تست SL نامعتبر LONG"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.stop_loss = 105.0  # SL > Entry
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_long_invalid_tp(self):
        """تست TP نامعتبر LONG"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.take_profit = 95.0  # TP < Entry
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_short_invalid_sl(self):
        """تست SL نامعتبر SHORT"""
        engine = self.get_engine()
        ra = create_short_risk_assessment()
        ra.stop_loss = 95.0  # SL < Entry
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_short_invalid_tp(self):
        """تست TP نامعتبر SHORT"""
        engine = self.get_engine()
        ra = create_short_risk_assessment()
        ra.take_profit = 105.0  # TP > Entry
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_zero_quantity_rejected(self):
        """تست Quantity صفر"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.position_size = 0.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_negative_quantity_rejected(self):
        """تست Quantity منفی"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.position_size = -10.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_invalid_notional_rejected(self):
        """تست Notional نامعتبر"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.notional_value = 0.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_invalid_risk_amount_rejected(self):
        """تست Risk Amount نامعتبر"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        ra.risk_amount = 0.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
    
    def test_inconsistent_risk_rejected(self):
        """تست Risk ناسازگار"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        # قیمت‌ها: Entry=100, SL=98 → Price Risk=2
        # Position Size=50 → Expected Risk=100
        # اما Risk Amount=200 → ناسازگار
        ra.risk_amount = 200.0
        ra.is_valid = False
        
        result = engine.create_order(ra)
        
        assert not result.success
        assert any("Risk inconsistency" in e for e in result.errors)
    
    def test_duplicate_signal_rejected(self):
        """تست سیگنال تکراری"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        
        result1 = engine.create_order(ra)
        result2 = engine.create_order(ra)
        
        assert result1.success
        assert not result2.success
        assert any("Duplicate" in e for e in result2.errors)
    
    def test_determinism(self):
        """تست قطعیت"""
        engine1 = self.get_engine()
        engine2 = self.get_engine()
        ra = create_long_risk_assessment()
        
        result1 = engine1.create_order(ra)
        result2 = engine2.create_order(ra)
        
        assert result1.success == result2.success
        if result1.order and result2.order:
            assert result1.order.entry_price == result2.order.entry_price
            assert result1.order.stop_loss == result2.order.stop_loss
            assert result1.order.quantity == result2.order.quantity
    
    def test_dry_run_no_real_order(self):
        """تست Dry Run بدون ارسال واقعی"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        
        result = engine.create_order(ra)
        
        assert result.success
        assert result.mode == ExecutionMode.DRY_RUN
        assert result.order is not None
        assert result.order.status == OrderStatus.VALIDATED
        # هیچ اتصال واقعی وجود ندارد
    
    def test_no_market_data_dependency(self):
        """تست عدم وابستگی به Market Data"""
        engine = self.get_engine()
        ra = create_long_risk_assessment()
        
        # Execution فقط از RiskAssessment استفاده می‌کند
        result = engine.create_order(ra)
        
        assert result.success
        # هیچ داده آینده یا Market Data وارد نمی‌شود
        assert result.order.timestamp == ra.timestamp
