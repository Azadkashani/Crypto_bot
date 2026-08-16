# FILE: src/strategy/trade/trade_signal_engine.py

"""
Trade Signal Engine — تولید سیگنال معاملاتی از Signal Quality
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..types.ftr_types import FTRZone, FTBEvent
from ..types.market_structure import StructureLevel, StructureType
from ..signal.signal_quality_types import (
    SignalQualityResult, SignalClassification
)
from .trade_signal_types import TradeSignal


class TradeSignalEngine:
    """
    تولید Trade Signal از SignalQualityResult
    """
    
    MIN_TP_DISTANCE_PCT = 0.005  # حداقل 0.5%
    MIN_RR_RATIO = 0.5  # حداقل R:R = 1:0.5 (ریسک بیشتر مجاز)
    
    def __init__(self):
        self._signal_counter = 0
    
    def reset(self):
        self._signal_counter = 0
    
    def create_trade_signal(
        self,
        signal_quality: SignalQualityResult,
        zone: FTRZone,
        ftb_event: FTBEvent,
        structure_levels: List[StructureLevel]
    ) -> Optional[TradeSignal]:
        """ایجاد Trade Signal"""
        if signal_quality.classification != SignalClassification.QUALIFIED:
            return None
        
        entry_price = self._calculate_entry_price(ftb_event, zone)
        stop_loss = self._calculate_stop_loss(zone)
        
        # TP: اول از ساختار، بعد از Impulse Projection
        take_profit = self._calculate_take_profit(zone, entry_price, structure_levels)
        
        if take_profit is None:
            # Fallback: استفاده از Impulse Distance
            take_profit = self._calculate_impulse_projection_tp(zone, entry_price)
        
        if entry_price is None or stop_loss is None or take_profit is None:
            return None
        
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk <= 0:
            return None
        
        risk_reward = reward / risk
        
        # بررسی حداقل R:R — Relax شده
        if risk_reward < self.MIN_RR_RATIO:
            return None
        
        self._signal_counter += 1
        signal_id = f"TS_{self._signal_counter}_{signal_quality.timestamp}"
        
        trade_signal = TradeSignal(
            signal_id=signal_id,
            symbol=zone.symbol,
            timeframe=zone.timeframe,
            direction=zone.direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            signal_quality_score=signal_quality.score,
            signal_quality_classification=signal_quality.classification.value,
            zone_id=zone.zone_id,
            created_timestamp=signal_quality.timestamp,
            metadata={
                'ftb_price': ftb_event.price,
                'zone_high': zone.zone_high,
                'zone_low': zone.zone_low,
                'invalidation_level': zone.invalidation_level,
                'tp_source': 'structure' if self._from_structure else 'impulse_projection',
            }
        )
        
        if not trade_signal.validate():
            return None
        
        return trade_signal
    
    def _calculate_entry_price(self, ftb_event: FTBEvent, zone: FTRZone) -> Optional[float]:
        if ftb_event is None:
            return zone.zone_midpoint
        return ftb_event.price
    
    def _calculate_stop_loss(self, zone: FTRZone) -> Optional[float]:
        if zone.invalidation_level is None:
            return None
        return zone.invalidation_level
    
    def _calculate_take_profit(
        self,
        zone: FTRZone,
        entry_price: float,
        structure_levels: List[StructureLevel]
    ) -> Optional[float]:
        """
        محاسبه TP از ساختار بازار با حداقل فاصله
        """
        self._from_structure = True
        
        if zone.direction == "LONG":
            valid_resistances = []
            for level in structure_levels:
                if level.level_type in ["RESISTANCE", "SUPPLY"]:
                    if level.price > entry_price:
                        distance_pct = (level.price - entry_price) / entry_price
                        if distance_pct >= self.MIN_TP_DISTANCE_PCT:
                            valid_resistances.append(level)
            
            if valid_resistances:
                nearest = min(valid_resistances, key=lambda l: l.price)
                return nearest.price
            return None
        
        elif zone.direction == "SHORT":
            valid_supports = []
            for level in structure_levels:
                if level.level_type in ["SUPPORT", "DEMAND"]:
                    if level.price < entry_price:
                        distance_pct = (entry_price - level.price) / entry_price
                        if distance_pct >= self.MIN_TP_DISTANCE_PCT:
                            valid_supports.append(level)
            
            if valid_supports:
                nearest = max(valid_supports, key=lambda l: l.price)
                return nearest.price
            return None
        
        return None
    
    def _calculate_impulse_projection_tp(
        self,
        zone: FTRZone,
        entry_price: float
    ) -> Optional[float]:
        """
        Fallback TP: استفاده از اندازه Impulse
        """
        self._from_structure = False
        
        if zone.displacement is None:
            return None
        
        impulse_distance = zone.displacement.distance
        
        if impulse_distance <= 0:
            return None
        
        # پروجکشن: 50% از فاصله Impulse
        projection = impulse_distance * 0.5
        
        if zone.direction == "LONG":
            tp = entry_price + projection
        else:
            tp = entry_price - projection
        
        # بررسی حداقل فاصله
        distance_pct = abs(tp - entry_price) / entry_price
        if distance_pct < self.MIN_TP_DISTANCE_PCT:
            return None
        
        return tp
