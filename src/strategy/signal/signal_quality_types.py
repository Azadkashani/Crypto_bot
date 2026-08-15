# FILE: src/strategy/signal/signal_quality_types.py

"""
تایپ‌های مخصوص Signal Quality Layer
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class SignalClassification(Enum):
    """طبقه‌بندی کیفیت سیگنال"""
    QUALIFIED = "QUALIFIED"
    WATCH = "WATCH"
    REJECTED = "REJECTED"


@dataclass
class ComponentScores:
    """امتیاز هر بخش از تحلیل"""
    structure_score: float = 0.0
    displacement_score: float = 0.0
    base_score: float = 0.0
    zone_score: float = 0.0
    ftb_score: float = 0.0
    trend_score: float = 0.0
    
    @property
    def total(self) -> float:
        """مجموع امتیازها"""
        return (
            self.structure_score +
            self.displacement_score +
            self.base_score +
            self.zone_score +
            self.ftb_score +
            self.trend_score
        )


@dataclass
class SignalQualityConfig:
    """پیکربندی Signal Quality Engine"""
    # وزن‌ها
    structure_weight: float = 20.0
    displacement_weight: float = 20.0
    base_weight: float = 15.0
    zone_weight: float = 15.0
    ftb_weight: float = 20.0
    trend_weight: float = 10.0
    
    # آستانه‌های طبقه‌بندی
    min_qualified_score: float = 80.0
    min_watch_score: float = 60.0
    
    # پارامترهای امتیازدهی
    good_displacement_candles: int = 4
    good_base_candles: int = 4
    max_base_candles: int = 15
    shallow_touch_depth_pct: float = 0.3
    deep_touch_depth_pct: float = 0.7
    
    def validate(self) -> List[str]:
        errors = []
        total_weight = (
            self.structure_weight +
            self.displacement_weight +
            self.base_weight +
            self.zone_weight +
            self.ftb_weight +
            self.trend_weight
        )
        
        if abs(total_weight - 100.0) > 0.01:
            errors.append(f"Total weight must equal 100, got {total_weight}")
        
        if self.min_qualified_score <= self.min_watch_score:
            errors.append("min_qualified_score must be > min_watch_score")
        
        if self.min_watch_score <= 0:
            errors.append("min_watch_score must be > 0")
        
        return errors


@dataclass
class SignalQualityResult:
    """نتیجه ارزیابی کیفیت سیگنال"""
    signal_id: str
    symbol: str
    timeframe: str
    direction: str
    score: float
    classification: SignalClassification
    component_scores: ComponentScores
    positive_factors: List[str] = field(default_factory=list)
    warning_factors: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    timestamp: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_qualified(self) -> bool:
        return self.classification == SignalClassification.QUALIFIED
    
    @property
    def is_watch(self) -> bool:
        return self.classification == SignalClassification.WATCH
    
    @property
    def is_rejected(self) -> bool:
        return self.classification == SignalClassification.REJECTED
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری برای لاگ‌گیری"""
        return {
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'direction': self.direction,
            'score': self.score,
            'classification': self.classification.value,
            'component_scores': {
                'structure': self.component_scores.structure_score,
                'displacement': self.component_scores.displacement_score,
                'base': self.component_scores.base_score,
                'zone': self.component_scores.zone_score,
                'ftb': self.component_scores.ftb_score,
                'trend': self.component_scores.trend_score,
            },
            'positive_factors': self.positive_factors,
            'warning_factors': self.warning_factors,
            'rejection_reasons': self.rejection_reasons,
            'timestamp': self.timestamp,
        }
