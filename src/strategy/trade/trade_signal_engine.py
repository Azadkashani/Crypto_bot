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
    
    این کلاس مستقل از FTR Core و Signal Quality است.
    فقط سیگنال‌های QUALIFIED را به TradeSignal تبدیل می‌کند.
    """
    
    def __init__(self):
        self._signal_counter = 0
    
    def reset(self):
        """بازنشانی شمارنده"""
        self._signal_counter = 0
    
    def create_trade_signal(
        self,
        signal_quality: SignalQualityResult,
        zone: FTRZone,
        ftb_event: FTBEvent,
        structure_levels: List[StructureLevel]
    ) -> Optional[TradeSignal]:
        """
        ایجاد Trade Signal از Signal Quality Result
        
        فقط سیگنال‌های QUALIFIED به TradeSignal تبدیل می‌شوند.
        
        Args:
            signal_quality: نتیجه ارزیابی کیفیت
            zone: FTR Zone
            ftb_event: رویداد FTB
            structure_levels: سطوح ساختاری موجود
        
        Returns:
            TradeSignal یا None اگر سیگنال QUALIFIED نباشد
        """
        # فقط سیگنال‌های QUALIFIED
        if signal_quality.classification != SignalClassification.QUALIFIED:
            return None
        
        # تعیین قیمت ورود از FTB
        entry_price = self._calculate_entry_price(ftb_event, zone)
        
        # تعیین Stop Loss از invalidation level
        stop_loss = self._calculate_stop_loss(zone)
        
        # تعیین Take Profit از ساختار بازار
        take_profit = self._calculate_take_profit(
            zone, entry_price, structure_levels
        )
        
        if entry_price is None or stop_loss is None or take_profit is None:
            return None
        
        # محاسبه R:R
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk <= 0:
            return None
        
        risk_reward = reward / risk
        
        # ایجاد TradeSignal
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
                'positive_factors': signal_quality.positive_factors,
                'warning_factors': signal_quality.warning_factors,
            }
        )
        
        # اعتبارسنجی
        if not trade_signal.validate():
            return None
        
        return trade_signal
    
    def _calculate_entry_price(
        self,
        ftb_event: FTBEvent,
        zone: FTRZone
    ) -> Optional[float]:
        """
        محاسبه قیمت ورود از FTB
        
        برای LONG: قیمت لمس (یا میانه Zone)
        برای SHORT: قیمت لمس (یا میانه Zone)
        """
        if ftb_event is None:
            return zone.zone_midpoint
        
        return ftb_event.price
    
    def _calculate_stop_loss(
        self,
        zone: FTRZone
    ) -> Optional[float]:
        """
        محاسبه Stop Loss از invalidation level Zone
        """
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
        محاسبه Take Profit بر اساس ساختار بازار
        
        برای LONG: نزدیک‌ترین مقاومت بالای Entry
        برای SHORT: نزدیک‌ترین حمایت زیر Entry
        """
        if zone.direction == "LONG":
            # جستجوی نزدیک‌ترین مقاومت بالای Entry
            resistances = [
                l for l in structure_levels
                if l.level_type in ["RESISTANCE", "SUPPLY"]
                and l.price > entry_price
            ]
            
            if not resistances:
                return None
            
            # نزدیک‌ترین مقاومت
            nearest = min(resistances, key=lambda l: l.price)
            return nearest.price
        
        elif zone.direction == "SHORT":
            # جستجوی نزدیک‌ترین حمایت زیر Entry
            supports = [
                l for l in structure_levels
                if l.level_type in ["SUPPORT", "DEMAND"]
                and l.price < entry_price
            ]
            
            if not supports:
                return None
            
            nearest = max(supports, key=lambda l: l.price)
            return nearest.price
        
        return None
