# FILE: src/strategy/execution/execution_engine.py

"""
Execution Engine — ساخت و اعتبارسنجی سفارش معاملاتی
"""

from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from ..risk.risk_types import RiskAssessment
from .execution_types import (
    OrderType, OrderStatus, ExecutionOrder,
    ExecutionResult, ExecutionMode
)


@dataclass
class ExecutionConfig:
    """پیکربندی Execution Engine"""
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    order_type: OrderType = OrderType.LIMIT
    risk_consistency_tolerance_pct: float = 1.0  # درصد تلرانس برای بررسی consistency
    
    def validate(self) -> List[str]:
        errors = []
        if self.risk_consistency_tolerance_pct < 0:
            errors.append("risk_consistency_tolerance_pct must be >= 0")
        return errors


class ExecutionEngine:
    """
    Execution Engine — تبدیل Risk Assessment به Execution Order
    
    این کلاس مستقل از FTR Core، Signal Quality، Trade Signal و Risk Management است.
    فقط Order Construction و Validation را انجام می‌دهد.
    """
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
        self._processed_signal_ids: Set[str] = set()
        self._order_counter = 0
    
    def reset(self):
        """بازنشانی وضعیت"""
        self._processed_signal_ids.clear()
        self._order_counter = 0
    
    def create_order(
        self,
        risk_assessment: RiskAssessment
    ) -> ExecutionResult:
        """
        ساخت سفارش از Risk Assessment
        
        Args:
            risk_assessment: نتیجه ارزیابی ریسک
        
        Returns:
            ExecutionResult
        """
        errors = []
        warnings = []
        
        # بررسی حالت اجرا
        if self.config.mode != ExecutionMode.DRY_RUN:
            warnings.append(f"Mode is {self.config.mode.value} — no real execution in this phase")
        
        # بررسی Duplicate
        if risk_assessment.signal_id in self._processed_signal_ids:
            errors.append(f"Duplicate signal_id: {risk_assessment.signal_id}")
            return ExecutionResult(
                success=False,
                errors=errors,
                warnings=warnings,
                mode=self.config.mode
            )
        
        # اعتبارسنجی Symbol
        if not risk_assessment.symbol or risk_assessment.symbol.strip() == "":
            errors.append("Invalid symbol: empty")
        
        # اعتبارسنجی Direction
        if risk_assessment.direction not in ["LONG", "SHORT"]:
            errors.append(f"Invalid direction: {risk_assessment.direction}")
        
        # اعتبارسنجی Entry
        if risk_assessment.entry_price <= 0:
            errors.append(f"Invalid entry price: {risk_assessment.entry_price}")
        
        # اعتبارسنجی Stop Loss
        if risk_assessment.stop_loss <= 0:
            errors.append(f"Invalid stop loss: {risk_assessment.stop_loss}")
        
        # اعتبارسنجی Take Profit
        if risk_assessment.take_profit <= 0:
            errors.append(f"Invalid take profit: {risk_assessment.take_profit}")
        
        # اعتبارسنجی Quantity
        if risk_assessment.position_size <= 0:
            errors.append(f"Invalid position size: {risk_assessment.position_size}")
        
        # اعتبارسنجی Notional
        if risk_assessment.notional_value <= 0:
            errors.append(f"Invalid notional: {risk_assessment.notional_value}")
        
        # اعتبارسنجی Risk Amount
        if risk_assessment.risk_amount <= 0:
            errors.append(f"Invalid risk amount: {risk_assessment.risk_amount}")
        
        # اعتبارسنجی هندسه LONG
        if risk_assessment.direction == "LONG":
            if risk_assessment.stop_loss >= risk_assessment.entry_price:
                errors.append("LONG: stop_loss must be < entry_price")
            if risk_assessment.take_profit <= risk_assessment.entry_price:
                errors.append("LONG: take_profit must be > entry_price")
        
        # اعتبارسنجی هندسه SHORT
        if risk_assessment.direction == "SHORT":
            if risk_assessment.stop_loss <= risk_assessment.entry_price:
                errors.append("SHORT: stop_loss must be > entry_price")
            if risk_assessment.take_profit >= risk_assessment.entry_price:
                errors.append("SHORT: take_profit must be < entry_price")
        
        # بررسی Risk Consistency
        # این بررسی قبل از is_valid انجام می‌شود تا inconsistency مشخص شود
        if risk_assessment.position_size > 0 and risk_assessment.entry_price > 0:
            expected_risk = risk_assessment.position_size * abs(
                risk_assessment.entry_price - risk_assessment.stop_loss
            )
            actual_risk = risk_assessment.risk_amount
            
            if expected_risk > 0:
                tolerance = self.config.risk_consistency_tolerance_pct / 100.0
                deviation = abs(expected_risk - actual_risk) / expected_risk
                
                if deviation > tolerance:
                    errors.append(
                        f"Risk inconsistency: expected={expected_risk:.6f}, "
                        f"actual={actual_risk:.6f}, deviation={deviation:.4f}"
                    )
        
        # بررسی Risk Assessment معتبر
        if not risk_assessment.is_valid:
            errors.append("Risk assessment is invalid")
            errors.extend([r.value for r in risk_assessment.rejection_reasons])
        
        # اگر خطا وجود دارد
        if errors:
            return ExecutionResult(
                success=False,
                errors=errors,
                warnings=warnings,
                mode=self.config.mode
            )
        
        # ساخت Order
        self._order_counter += 1
        order_id = f"ORD_{self._order_counter}_{risk_assessment.signal_id}"
        
        order = ExecutionOrder(
            order_id=order_id,
            signal_id=risk_assessment.signal_id,
            symbol=risk_assessment.symbol,
            direction=risk_assessment.direction,
            order_type=self.config.order_type,
            entry_price=risk_assessment.entry_price,
            quantity=risk_assessment.position_size,
            stop_loss=risk_assessment.stop_loss,
            take_profit=risk_assessment.take_profit,
            notional=risk_assessment.notional_value,
            status=OrderStatus.VALIDATED,
            timestamp=risk_assessment.timestamp,
            metadata={
                'risk_amount': risk_assessment.risk_amount,
                'risk_reward': risk_assessment.risk_reward,
                'zone_id': risk_assessment.metadata.get('zone_id', ''),
                'signal_quality_score': risk_assessment.metadata.get('signal_quality_score', 0),
            }
        )
        
        # ثبت signal_id
        self._processed_signal_ids.add(risk_assessment.signal_id)
        
        return ExecutionResult(
            success=True,
            order=order,
            errors=[],
            warnings=warnings,
            mode=self.config.mode
        )