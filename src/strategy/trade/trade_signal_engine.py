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
    
    MIN_TP_DISTANCE_PCT = 0.005  # حداقل 0.5% فاصله TP از Entry
    MIN_RR_RATIO = 1.0  # حداقل R:R = 1:1
    
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
        take_profit = self._calculate_take_profit(zone, entry_price, structure_levels)
        
        if entry_price is None or stop_loss is None or take_profit is None:
            return None
        
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk <= 0:
            return None
        
        risk_reward = reward / risk
        
        # بررسی حداقل R:R
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
                'ftb_touch_type': ftb_event.touch_type.value if ftb_event.touch_type else None,
                'zone_high': zone.zone_high,
                'zone_low': zone.zone_low,
                'invalidation_level': zone.invalidation_level,
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
        محاسبه TP با حداقل فاصله 0.5% از Entry
        """
        if zone.direction == "LONG":
            valid_resistances = []
            for level in structure_levels:
                if level.level_type in ["RESISTANCE", "SUPPLY"]:
                    if level.price > entry_price:
                        distance_pct = (level.price - entry_price) / entry_price
                        if distance_pct >= self.MIN_TP_DISTANCE_PCT:
                            valid_resistances.append(level)
            
            if not valid_resistances:
                return None
            
            nearest = min(valid_resistances, key=lambda l: l.price)
            return nearest.price
        
        elif zone.direction == "SHORT":
            valid_supports = []
            for level in structure_levels:
                if level.level_type in ["SUPPORT", "DEMAND"]:
                    if level.price < entry_price:
                        distance_pct = (entry_price - level.price) / entry_price
                        if distance_pct >= self.MIN_TP_DISTANCE_PCT:
                            valid_supports.append(level)
            
            if not valid_supports:
                return None
            
            nearest = max(valid_supports, key=lambda l: l.price)
            return nearest.price
        
        return None
