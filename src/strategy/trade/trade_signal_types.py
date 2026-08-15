# FILE: src/strategy/trade/trade_signal_types.py

"""
تایپ‌های مخصوص Trade Signal Layer
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class TradeSignalDirection(Enum):
    """جهت سیگنال معاملاتی"""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class TradeSignal:
    """سیگنال معاملاتی کامل"""
    signal_id: str
    symbol: str
    timeframe: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    signal_quality_score: float
    signal_quality_classification: str
    zone_id: str
    created_timestamp: int
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def risk(self) -> float:
        """میزان ریسک (فاصله Entry تا SL)"""
        return abs(self.entry_price - self.stop_loss)
    
    @property
    def reward(self) -> float:
        """میزان پاداش (فاصله Entry تا TP)"""
        return abs(self.take_profit - self.entry_price)
    
    def validate(self) -> bool:
        """اعتبارسنجی سیگنال"""
        self.validation_errors = []
        
        if self.entry_price <= 0:
            self.validation_errors.append("Invalid entry price")
        
        if self.stop_loss <= 0:
            self.validation_errors.append("Invalid stop loss")
        
        if self.take_profit <= 0:
            self.validation_errors.append("Invalid take profit")
        
        if self.direction == "LONG":
            if self.stop_loss >= self.entry_price:
                self.validation_errors.append("LONG: stop_loss must be < entry_price")
            if self.take_profit <= self.entry_price:
                self.validation_errors.append("LONG: take_profit must be > entry_price")
        elif self.direction == "SHORT":
            if self.stop_loss <= self.entry_price:
                self.validation_errors.append("SHORT: stop_loss must be > entry_price")
            if self.take_profit >= self.entry_price:
                self.validation_errors.append("SHORT: take_profit must be < entry_price")
        else:
            self.validation_errors.append(f"Invalid direction: {self.direction}")
        
        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'risk_reward': self.risk_reward,
            'signal_quality_score': self.signal_quality_score,
            'signal_quality_classification': self.signal_quality_classification,
            'zone_id': self.zone_id,
            'created_timestamp': self.created_timestamp,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'metadata': self.metadata,
        }
