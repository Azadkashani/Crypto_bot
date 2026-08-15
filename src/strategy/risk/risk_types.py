# FILE: src/strategy/risk/risk_types.py

"""
تایپ‌های مخصوص Risk Management Layer
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class RiskRejectionReason(Enum):
    """دلایل رد ارزیابی ریسک"""
    INVALID_EQUITY = "INVALID_EQUITY"
    INVALID_RISK_PERCENT = "INVALID_RISK_PERCENT"
    INVALID_TRADE_SIGNAL = "INVALID_TRADE_SIGNAL"
    INVALID_STOP_DISTANCE = "INVALID_STOP_DISTANCE"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    RR_BELOW_MINIMUM = "RR_BELOW_MINIMUM"
    INVALID_ENTRY = "INVALID_ENTRY"
    INVALID_STOP_LOSS = "INVALID_STOP_LOSS"
    INVALID_TAKE_PROFIT = "INVALID_TAKE_PROFIT"
    INVALID_POSITION_SIZE = "INVALID_POSITION_SIZE"


@dataclass
class RiskConfig:
    """پیکربندی مدیریت ریسک"""
    risk_per_trade_pct: float = 1.0  # درصد ریسک هر معامله از equity
    max_risk_per_trade_pct: float = 5.0  # حداکثر ریسک مجاز
    min_risk_reward: float = 0.0  # حداقل R:R (0 = بدون محدودیت)
    max_position_notional: Optional[float] = None  # حداکثر ارزش Notional پوزیشن
    
    def validate(self) -> List[str]:
        errors = []
        if self.risk_per_trade_pct <= 0:
            errors.append("risk_per_trade_pct must be > 0")
        if self.max_risk_per_trade_pct <= 0:
            errors.append("max_risk_per_trade_pct must be > 0")
        if self.risk_per_trade_pct > self.max_risk_per_trade_pct:
            errors.append("risk_per_trade_pct must be <= max_risk_per_trade_pct")
        if self.min_risk_reward < 0:
            errors.append("min_risk_reward must be >= 0")
        if self.max_position_notional is not None and self.max_position_notional <= 0:
            errors.append("max_position_notional must be > 0")
        return errors


@dataclass
class RiskAssessment:
    """نتیجه ارزیابی ریسک و محاسبه اندازه پوزیشن"""
    assessment_id: str
    signal_id: str
    symbol: str
    direction: str
    account_equity: float
    risk_per_trade_pct: float
    risk_amount: float
    entry_price: float
    stop_loss: float
    take_profit: float
    price_risk: float
    position_size: float
    notional_value: float
    risk_reward: float
    is_valid: bool = True
    rejection_reasons: List[RiskRejectionReason] = field(default_factory=list)
    timestamp: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'assessment_id': self.assessment_id,
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'account_equity': self.account_equity,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'risk_amount': self.risk_amount,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'price_risk': self.price_risk,
            'position_size': self.position_size,
            'notional_value': self.notional_value,
            'risk_reward': self.risk_reward,
            'is_valid': self.is_valid,
            'rejection_reasons': [r.value for r in self.rejection_reasons],
            'timestamp': self.timestamp,
            'metadata': self.metadata,
        }
