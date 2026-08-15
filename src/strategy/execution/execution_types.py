# FILE: src/strategy/execution/execution_types.py

"""
تایپ‌های مخصوص Execution Layer
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class OrderType(Enum):
    """نوع سفارش"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):
    """وضعیت سفارش"""
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ExecutionMode(Enum):
    """حالت اجرا"""
    DRY_RUN = "DRY_RUN"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass
class ExecutionOrder:
    """سفارش آماده اجرا"""
    order_id: str
    signal_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    order_type: OrderType
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    notional: float
    status: OrderStatus = OrderStatus.CREATED
    timestamp: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'order_id': self.order_id,
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'order_type': self.order_type.value,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'notional': self.notional,
            'status': self.status.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
        }


@dataclass
class ExecutionResult:
    """نتیجه اجرای سفارش"""
    success: bool
    order: Optional[ExecutionOrder] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'success': self.success,
            'order': self.order.to_dict() if self.order else None,
            'errors': self.errors,
            'warnings': self.warnings,
            'mode': self.mode.value,
        }
