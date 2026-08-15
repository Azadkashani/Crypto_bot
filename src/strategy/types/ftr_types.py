# FILE: src/strategy/types/ftr_types.py

"""
تایپ‌های مخصوص تشخیص FTR
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from .market_structure import (
    StructureLevel, 
    StructureBreak, 
    SwingPoint,
    MarketStructureState
)


class FTRDirection(Enum):
    """جهت FTR"""
    LONG = "LONG"
    SHORT = "SHORT"


class FTRZoneState(Enum):
    """وضعیت‌های چرخه حیات FTR Zone"""
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FIRST_TOUCH = "FIRST_TOUCH"
    USED = "USED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class FTBTouchType(Enum):
    """نوع لمس FTB"""
    WICK = "WICK"
    CLOSE = "CLOSE"
    PENETRATION = "PENETRATION"


@dataclass
class DisplacementData:
    """داده حرکت جابجایی (Displacement)"""
    start_price: float
    end_price: float
    start_timestamp: int
    end_timestamp: int
    direction: str  # "LONG", "SHORT"
    distance: float = 0.0
    candle_count: int = 0
    strength_score: float = 0.0
    avg_candle_range: float = 0.0
    start_index: int = 0
    end_index: int = 0
    
    def __post_init__(self):
        if self.direction == "LONG":
            self.distance = self.end_price - self.start_price
        elif self.direction == "SHORT":
            self.distance = self.start_price - self.end_price
        else:
            self.distance = 0.0
        
        if self.distance < 0:
            self.distance = abs(self.distance)
    
    @property
    def is_valid(self) -> bool:
        """بررسی اعتبار جابجایی"""
        return self.candle_count > 0 and self.distance > 0


@dataclass
class BaseData:
    """داده ناحیه Base/Consolidation"""
    high: float
    low: float
    start_timestamp: int
    end_timestamp: int
    start_index: int = 0
    end_index: int = 0
    duration_bars: int = 0
    height: float = 0.0
    quality_score: float = 0.0
    compression_ratio: float = 0.0
    
    def __post_init__(self):
        self.duration_bars = self.end_index - self.start_index + 1
        self.height = self.high - self.low
        
        if self.height < 0:
            self.height = abs(self.height)
    
    @property
    def midpoint(self) -> float:
        """نقطه میانی Base"""
        return (self.high + self.low) / 2.0
    
    @property
    def is_valid(self) -> bool:
        """بررسی اعتبار Base"""
        return self.duration_bars >= 1 and self.height > 0


@dataclass
class FTRZone:
    """یک FTR Zone کامل"""
    zone_id: str
    symbol: str
    timeframe: str
    direction: str  # "LONG", "SHORT"
    zone_high: float
    zone_low: float
    zone_midpoint: float
    created_timestamp: int
    structure_reference: Optional[StructureLevel] = None
    structure_break: Optional[StructureBreak] = None
    displacement: Optional[DisplacementData] = None
    base: Optional[BaseData] = None
    invalidation_level: Optional[float] = None
    state: FTRZoneState = FTRZoneState.CREATED
    first_touch_timestamp: Optional[int] = None
    first_touch_price: Optional[float] = None
    first_touch_type: Optional[FTBTouchType] = None
    touch_count: int = 0
    last_touch_timestamp: Optional[int] = None
    target_candidates: List[float] = field(default_factory=list)
    diagnostic_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.zone_midpoint == 0.0:
            self.zone_midpoint = (self.zone_high + self.zone_low) / 2.0
        
        if self.invalidation_level is None:
            if self.direction == "LONG":
                self.invalidation_level = self.zone_low
            elif self.direction == "SHORT":
                self.invalidation_level = self.zone_high
    
    @property
    def zone_height(self) -> float:
        """ارتفاع Zone"""
        return abs(self.zone_high - self.zone_low)
    
    @property
    def is_active(self) -> bool:
        """بررسی فعال بودن Zone"""
        return self.state in [FTRZoneState.CREATED, FTRZoneState.ACTIVE, FTRZoneState.FIRST_TOUCH]
    
    def is_price_in_zone(self, price: float) -> bool:
        """بررسی اینکه آیا قیمت داخل Zone است"""
        return self.zone_low <= price <= self.zone_high
    
    def update_state(self, new_state: FTRZoneState):
        """به‌روزرسانی وضعیت Zone"""
        self.state = new_state
    
    def register_touch(self, price: float, timestamp: int, touch_type: FTBTouchType):
        """ثبت یک لمس Zone"""
        self.touch_count += 1
        self.last_touch_timestamp = timestamp
        
        if self.first_touch_timestamp is None:
            self.first_touch_timestamp = timestamp
            self.first_touch_price = price
            self.first_touch_type = touch_type
            self.update_state(FTRZoneState.FIRST_TOUCH)
    
    def invalidate(self, timestamp: int):
        """ابطال Zone"""
        self.update_state(FTRZoneState.INVALIDATED)
        self.diagnostic_info["invalidation_timestamp"] = timestamp
    
    def consume(self, timestamp: int):
        """مصرف Zone (استفاده شده)"""
        self.update_state(FTRZoneState.USED)
        self.diagnostic_info["consumed_timestamp"] = timestamp
    
    def expire(self, timestamp: int):
        """منقضی کردن Zone"""
        self.update_state(FTRZoneState.EXPIRED)
        self.diagnostic_info["expired_timestamp"] = timestamp


@dataclass
class FTBEvent:
    """رویداد First Time Back"""
    zone: FTRZone
    timestamp: int
    price: float
    touch_type: FTBTouchType
    penetration_depth: float = 0.0
    is_valid: bool = False
    validation_reasons: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """محاسبه عمق نفوذ به Zone"""
        if self.zone.direction == "LONG":
            if self.price <= self.zone.zone_low:
                self.penetration_depth = self.zone.zone_low - self.price
            else:
                self.penetration_depth = self.price - self.zone.zone_low
        elif self.zone.direction == "SHORT":
            if self.price >= self.zone.zone_high:
                self.penetration_depth = self.price - self.zone.zone_high
            else:
                self.penetration_depth = self.zone.zone_high - self.price
        
        self.penetration_depth = abs(self.penetration_depth)


@dataclass
class FTRDetectionResult:
    """نتیجه کامل تشخیص FTR"""
    zones: List[FTRZone] = field(default_factory=list)
    ftb_events: List[FTBEvent] = field(default_factory=list)
    structure_state: Optional[MarketStructureState] = None
    diagnostic_messages: List[str] = field(default_factory=list)
    
    def add_zone(self, zone: FTRZone):
        """افزودن Zone جدید"""
        self.zones.append(zone)
    
    def add_ftb(self, ftb: FTBEvent):
        """افزودن رویداد FTB"""
        self.ftb_events.append(ftb)
    
    def add_diagnostic(self, message: str):
        """افزودن پیام تشخیصی"""
        self.diagnostic_messages.append(message)