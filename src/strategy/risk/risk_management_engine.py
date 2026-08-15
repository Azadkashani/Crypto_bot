# FILE: src/strategy/risk/risk_management_engine.py

"""
Risk Management Engine — محاسبه ریسک و اندازه پوزیشن
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..trade.trade_signal_types import TradeSignal
from .risk_types import (
    RiskConfig, RiskAssessment, RiskRejectionReason
)


class RiskManagementEngine:
    """
    مدیریت ریسک و محاسبه اندازه پوزیشن
    
    این کلاس مستقل از FTR Core، Signal Quality و Trade Signal است.
    فقط Risk Assessment و Position Sizing را انجام می‌دهد.
    """
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self._assessment_counter = 0
    
    def reset(self):
        """بازنشانی شمارنده"""
        self._assessment_counter = 0
    
    def calculate_position_size(
        self,
        trade_signal: TradeSignal,
        account_equity: float,
        risk_per_trade_pct: Optional[float] = None
    ) -> RiskAssessment:
        """
        محاسبه ریسک و اندازه پوزیشن از TradeSignal
        
        Args:
            trade_signal: سیگنال معاملاتی
            account_equity: equity حساب
            risk_per_trade_pct: درصد ریسک (اختیاری — از config استفاده می‌شود اگر None)
        
        Returns:
            RiskAssessment
        """
        self._assessment_counter += 1
        assessment_id = f"RA_{self._assessment_counter}_{trade_signal.created_timestamp}"
        
        # استفاده از config یا پارامتر
        risk_pct = risk_per_trade_pct if risk_per_trade_pct is not None else self.config.risk_per_trade_pct
        
        rejection_reasons = []
        
        # اعتبارسنجی TradeSignal
        if not trade_signal.is_valid:
            rejection_reasons.append(RiskRejectionReason.INVALID_TRADE_SIGNAL)
        
        # اعتبارسنجی equity
        if account_equity <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_EQUITY)
        
        # اعتبارسنجی risk percent
        if risk_pct <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_RISK_PERCENT)
        elif risk_pct > self.config.max_risk_per_trade_pct:
            rejection_reasons.append(RiskRejectionReason.RISK_LIMIT_EXCEEDED)
        
        # اعتبارسنجی قیمت‌ها
        if trade_signal.entry_price <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_ENTRY)
        
        if trade_signal.stop_loss <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_STOP_LOSS)
        
        if trade_signal.take_profit <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_TAKE_PROFIT)
        
        # محاسبه price risk
        price_risk = abs(trade_signal.entry_price - trade_signal.stop_loss)
        
        if price_risk <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_STOP_DISTANCE)
        
        # بررسی R:R
        if self.config.min_risk_reward > 0:
            if trade_signal.risk_reward < self.config.min_risk_reward:
                rejection_reasons.append(RiskRejectionReason.RR_BELOW_MINIMUM)
        
        # محاسبه risk amount
        risk_amount = account_equity * risk_pct / 100.0
        
        # محاسبه position size
        position_size = 0.0
        if price_risk > 0:
            position_size = risk_amount / price_risk
        
        # محاسبه notional value
        notional_value = position_size * trade_signal.entry_price
        
        # بررسی notional limit
        if (
            self.config.max_position_notional is not None
            and notional_value > self.config.max_position_notional
        ):
            rejection_reasons.append(RiskRejectionReason.INVALID_POSITION_SIZE)
        
        # بررسی position size معتبر
        if position_size <= 0:
            rejection_reasons.append(RiskRejectionReason.INVALID_POSITION_SIZE)
        
        # ساخت RiskAssessment
        assessment = RiskAssessment(
            assessment_id=assessment_id,
            signal_id=trade_signal.signal_id,
            symbol=trade_signal.symbol,
            direction=trade_signal.direction,
            account_equity=account_equity,
            risk_per_trade_pct=risk_pct,
            risk_amount=risk_amount,
            entry_price=trade_signal.entry_price,
            stop_loss=trade_signal.stop_loss,
            take_profit=trade_signal.take_profit,
            price_risk=price_risk,
            position_size=position_size,
            notional_value=notional_value,
            risk_reward=trade_signal.risk_reward,
            is_valid=len(rejection_reasons) == 0,
            rejection_reasons=rejection_reasons,
            timestamp=trade_signal.created_timestamp,
            metadata={
                'zone_id': trade_signal.zone_id,
                'signal_quality_score': trade_signal.signal_quality_score,
                'signal_quality_classification': trade_signal.signal_quality_classification,
            }
        )
        
        return assessment
