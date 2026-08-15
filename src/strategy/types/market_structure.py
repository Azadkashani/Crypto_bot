# FILE: src/strategy/types/market_structure.py

"""
تایپ‌های پایه برای ساختار بازار
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class SwingType(Enum):
    """نوع Swing"""
    HIGH = "HIGH"
    LOW = "LOW"


class StructureType(Enum):
    """نوع ساختار بازار"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    TRANSITIONING = "TRANSITIONING"


class BreakType(Enum):
    """نوع شکست ساختار"""
    BOS = "BOS"  # Break of Structure
    CHOCH = "CHOCH"  # Change of Character


@dataclass
class SwingPoint:
    """یک نقطه Swing در داده قیمت"""
    price: float
    timestamp: int
    swing_type: SwingType
    index: int
    is_confirmed: bool = False
    confirmation_time: Optional[int] = None
    
    def __repr__(self) -> str:
        return f"SwingPoint({self.swing_type.value} @ {self.price:.8f}, ts={self.timestamp})"


@dataclass
class StructureLevel:
    """یک سطح مهم ساختاری"""
    price: float
    level_type: str  # "SUPPORT", "RESISTANCE", "DEMAND", "SUPPLY"
    created_timestamp: int
    last_touched_timestamp: Optional[int] = None
    touch_count: int = 0
    strength_score: float = 0.0
    is_consumed: bool = False
    reference_swings: List[SwingPoint] = field(default_factory=list)
    
    def __repr__(self) -> str:
        return f"StructureLevel({self.level_type} @ {self.price:.8f})"


@dataclass
class StructureBreak:
    """یک شکست ساختاری"""
    break_type: BreakType
    break_price: float
    break_timestamp: int
    broken_level: StructureLevel
    direction: str  # "LONG", "SHORT"
    is_valid: bool = False
    validation_timestamp: Optional[int] = None
    break_strength: float = 0.0
    
    def __repr__(self) -> str:
        return f"StructureBreak({self.direction} @ {self.break_price:.8f}, ts={self.break_timestamp})"


@dataclass
class MarketStructureState:
    """وضعیت فعلی ساختار بازار"""
    timeframe: str
    structure_type: StructureType
    current_swing_high: Optional[SwingPoint] = None
    current_swing_low: Optional[SwingPoint] = None
    last_break: Optional[StructureBreak] = None
    invalidation_level: Optional[float] = None
    swing_points: List[SwingPoint] = field(default_factory=list)
    structure_levels: List[StructureLevel] = field(default_factory=list)
    
    def is_bullish(self) -> bool:
        return self.structure_type == StructureType.BULLISH
    
    def is_bearish(self) -> bool:
        return self.structure_type == StructureType.BEARISH