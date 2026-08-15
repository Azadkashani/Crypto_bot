# FILE: src/strategy/signal/signal_quality_engine.py

"""
Signal Quality Engine — ارزیابی کیفیت FTR/FTB Setup
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import (
    StructureBreak, StructureLevel, BreakType, StructureType
)
from ..types.ftr_types import (
    FTRZone, FTBEvent, FTBTouchType, FTRZoneState,
    DisplacementData, BaseData
)
from .signal_quality_types import (
    SignalQualityConfig, SignalQualityResult,
    SignalClassification, ComponentScores
)


class SignalQualityEngine:
    """
    ارزیابی کیفیت سیگنال‌های FTR/FTB
    
    این کلاس مستقل از FTR Core است و فقط کیفیت Setup را ارزیابی می‌کند.
    """
    
    def __init__(self, config: Optional[SignalQualityConfig] = None):
        self.config = config or SignalQualityConfig()
        self._signal_counter = 0
    
    def reset(self):
        """بازنشانی شمارنده سیگنال"""
        self._signal_counter = 0
    
    def evaluate_signal(
        self,
        symbol: str,
        timeframe: str,
        zone: FTRZone,
        ftb_event: FTBEvent,
        structure_break: StructureBreak,
        market_structure_type: StructureType,
        timestamp: int,
        trend_direction: Optional[str] = None
    ) -> SignalQualityResult:
        """ارزیابی کیفیت یک Setup FTR/FTB"""
        self._signal_counter += 1
        signal_id = f"SIG_{self._signal_counter}_{timestamp}"
        
        structure_score, structure_positive, structure_warnings = self._score_structure(
            structure_break, market_structure_type
        )
        
        displacement_score, displacement_positive, displacement_warnings = self._score_displacement(
            zone.displacement
        )
        
        base_score, base_positive, base_warnings = self._score_base(zone.base)
        
        zone_score, zone_positive, zone_warnings = self._score_zone(zone)
        
        ftb_score, ftb_positive, ftb_warnings = self._score_ftb(ftb_event, zone)
        
        trend_score, trend_positive, trend_warnings = self._score_trend(
            zone.direction, trend_direction
        )
        
        component_scores = ComponentScores(
            structure_score=structure_score,
            displacement_score=displacement_score,
            base_score=base_score,
            zone_score=zone_score,
            ftb_score=ftb_score,
            trend_score=trend_score
        )
        
        total_score = component_scores.total
        classification = self._classify(total_score)
        
        positive_factors = (
            structure_positive + displacement_positive +
            base_positive + zone_positive + ftb_positive + trend_positive
        )
        
        warning_factors = (
            structure_warnings + displacement_warnings +
            base_warnings + zone_warnings + ftb_warnings + trend_warnings
        )
        
        rejection_reasons = []
        if classification == SignalClassification.REJECTED:
            rejection_reasons = warning_factors.copy()
        
        return SignalQualityResult(
            signal_id=signal_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=zone.direction,
            score=total_score,
            classification=classification,
            component_scores=component_scores,
            positive_factors=positive_factors,
            warning_factors=warning_factors,
            rejection_reasons=rejection_reasons,
            timestamp=timestamp,
            metadata={
                'zone_id': zone.zone_id,
                'break_type': structure_break.break_type.value,
                'ftb_touch_type': ftb_event.touch_type.value if ftb_event.touch_type else None,
                'ftb_penetration_ratio': self._calculate_ftb_penetration_ratio(ftb_event, zone),
                'zone_height': zone.zone_height,
            }
        )
    
    def _calculate_ftb_penetration_ratio(self, ftb_event: FTBEvent, zone: FTRZone) -> float:
        """
        محاسبه نسبت نفوذ FTB به Zone
        
        برای LONG: penetration = zone_high - touch_price
        برای SHORT: penetration = touch_price - zone_low
        
        نسبت = penetration / zone_height
        """
        if zone.zone_height <= 0:
            return 0.0
        
        if zone.direction == "LONG":
            penetration = zone.zone_high - ftb_event.price
        else:
            penetration = ftb_event.price - zone.zone_low
        
        # اگر قیمت خارج از Zone باشد، penetration منفی است
        penetration = max(0.0, penetration)
        
        return min(penetration / zone.zone_height, 1.0)
    
    def _score_structure(
        self,
        structure_break: StructureBreak,
        market_structure_type: StructureType
    ) -> tuple:
        """امتیازدهی به کیفیت ساختار"""
        score = 0.0
        positive = []
        warnings = []
        
        if structure_break.break_type == BreakType.BOS:
            score += self.config.structure_weight * 0.6
            positive.append("Strong BOS break")
        elif structure_break.break_type == BreakType.CHOCH:
            score += self.config.structure_weight * 0.4
            warnings.append("CHOCH break (not BOS)")
        
        if market_structure_type == StructureType.BULLISH and structure_break.direction == "LONG":
            score += self.config.structure_weight * 0.4
            positive.append("Bullish structure aligned")
        elif market_structure_type == StructureType.BEARISH and structure_break.direction == "SHORT":
            score += self.config.structure_weight * 0.4
            positive.append("Bearish structure aligned")
        else:
            warnings.append("Structure not aligned with break direction")
        
        if structure_break.break_strength >= 0.7:
            score += self.config.structure_weight * 0.3
            positive.append("Strong break strength")
        
        return min(score, self.config.structure_weight), positive, warnings
    
    def _score_displacement(self, displacement: Optional[DisplacementData]) -> tuple:
        """امتیازدهی به کیفیت جابجایی"""
        score = 0.0
        positive = []
        warnings = []
        
        if displacement is None or not displacement.is_valid:
            warnings.append("No valid displacement")
            return score, positive, warnings
        
        if displacement.distance > 0:
            score += self.config.displacement_weight * 0.3
            positive.append(f"Valid displacement: {displacement.distance:.4f}")
        
        if displacement.candle_count >= self.config.good_displacement_candles:
            score += self.config.displacement_weight * 0.3
            positive.append(f"Good displacement candles: {displacement.candle_count}")
        elif displacement.candle_count < 2:
            warnings.append(f"Weak displacement: only {displacement.candle_count} candles")
        
        if displacement.strength_score >= 0.6:
            score += self.config.displacement_weight * 0.4
            positive.append(f"Strong displacement: {displacement.strength_score:.2f}")
        elif displacement.strength_score < 0.4:
            warnings.append(f"Weak displacement strength: {displacement.strength_score:.2f}")
        
        return min(score, self.config.displacement_weight), positive, warnings
    
    def _score_base(self, base: Optional[BaseData]) -> tuple:
        """امتیازدهی به کیفیت Base"""
        score = 0.0
        positive = []
        warnings = []
        
        if base is None or not base.is_valid:
            warnings.append("No valid base")
            return score, positive, warnings
        
        if self.config.good_base_candles <= base.duration_bars <= self.config.max_base_candles:
            score += self.config.base_weight * 0.4
            positive.append(f"Good base duration: {base.duration_bars} candles")
        elif base.duration_bars < self.config.good_base_candles:
            warnings.append(f"Base too short: {base.duration_bars} candles")
        else:
            warnings.append(f"Base too long: {base.duration_bars} candles")
        
        if base.compression_ratio >= 0.3:
            score += self.config.base_weight * 0.3
            positive.append(f"Good base compression: {base.compression_ratio:.2f}")
        
        if base.quality_score >= 0.5:
            score += self.config.base_weight * 0.3
            positive.append(f"Good base quality: {base.quality_score:.2f}")
        elif base.quality_score < 0.3:
            warnings.append(f"Poor base quality: {base.quality_score:.2f}")
        
        return min(score, self.config.base_weight), positive, warnings
    
    def _score_zone(self, zone: FTRZone) -> tuple:
        """امتیازدهی به کیفیت Zone"""
        score = 0.0
        positive = []
        warnings = []
        
        if zone.zone_midpoint > 0:
            height_pct = zone.zone_height / zone.zone_midpoint
            
            if height_pct <= 0.02:
                score += self.config.zone_weight * 0.4
                positive.append(f"Tight zone: {height_pct:.4f}")
            elif height_pct > 0.05:
                warnings.append(f"Wide zone: {height_pct:.4f}")
        
        if zone.state == FTRZoneState.FIRST_TOUCH:
            score += self.config.zone_weight * 0.3
            positive.append("Zone in first touch state")
        elif zone.state == FTRZoneState.ACTIVE:
            score += self.config.zone_weight * 0.2
            positive.append("Zone active")
        
        if zone.invalidation_level is not None:
            if zone.direction == "LONG":
                if zone.invalidation_level < zone.zone_low:
                    score += self.config.zone_weight * 0.3
                    positive.append("Valid invalidation level")
            else:
                if zone.invalidation_level > zone.zone_high:
                    score += self.config.zone_weight * 0.3
                    positive.append("Valid invalidation level")
        
        return min(score, self.config.zone_weight), positive, warnings
    
    def _score_ftb(self, ftb_event: FTBEvent, zone: FTRZone) -> tuple:
        """امتیازدهی به کیفیت FTB با حساسیت به عمق نفوذ"""
        score = 0.0
        positive = []
        warnings = []
        
        if ftb_event is None or not ftb_event.is_valid:
            warnings.append("Invalid FTB")
            return score, positive, warnings
        
        # First Touch
        if zone.first_touch_timestamp is not None:
            score += self.config.ftb_weight * 0.3
            positive.append("First touch confirmed")
        
        # محاسبه نسبت نفوذ
        penetration_ratio = self._calculate_ftb_penetration_ratio(ftb_event, zone)
        
        # امتیازدهی بر اساس عمق نفوذ
        if penetration_ratio <= self.config.shallow_touch_depth_pct:
            score += self.config.ftb_weight * 0.4
            positive.append(f"Shallow touch: {penetration_ratio:.2f}")
        elif penetration_ratio <= 0.5:
            score += self.config.ftb_weight * 0.3
            positive.append(f"Moderate touch: {penetration_ratio:.2f}")
        elif penetration_ratio <= self.config.deep_touch_depth_pct:
            score += self.config.ftb_weight * 0.2
            warnings.append(f"Deep touch: {penetration_ratio:.2f}")
        else:
            score += self.config.ftb_weight * 0.1
            warnings.append(f"Very deep touch: {penetration_ratio:.2f}")
        
        # نوع لمس
        if ftb_event.touch_type == FTBTouchType.WICK:
            score += self.config.ftb_weight * 0.2
            positive.append("Wick touch (cleaner)")
        elif ftb_event.touch_type == FTBTouchType.PENETRATION:
            warnings.append("Deep penetration touch")
            # امتیاز اضافه برای penetration type
            score += self.config.ftb_weight * 0.1
        
        return min(score, self.config.ftb_weight), positive, warnings
    
    def _score_trend(
        self,
        zone_direction: str,
        trend_direction: Optional[str]
    ) -> tuple:
        """امتیازدهی به هم‌جهتی با روند"""
        score = 0.0
        positive = []
        warnings = []
        
        if trend_direction is None:
            score += self.config.trend_weight * 0.5
            warnings.append("No trend data available")
            return score, positive, warnings
        
        if zone_direction == trend_direction:
            score += self.config.trend_weight
            positive.append(f"Trend aligned: {trend_direction}")
        else:
            warnings.append(f"Trend conflict: zone={zone_direction}, trend={trend_direction}")
            score += self.config.trend_weight * 0.2
        
        return min(score, self.config.trend_weight), positive, warnings
    
    def _classify(self, total_score: float) -> SignalClassification:
        """طبقه‌بندی سیگنال بر اساس امتیاز"""
        if total_score >= self.config.min_qualified_score:
            return SignalClassification.QUALIFIED
        elif total_score >= self.config.min_watch_score:
            return SignalClassification.WATCH
        else:
            return SignalClassification.REJECTED