# FILE: src/strategy/config/trading_universe.py

"""
پیکربندی متمرکز Trading Universe و محدودیت‌های معاملاتی
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class MarginMode(Enum):
    """حالت مارجین"""
    ISOLATED = "isolated"
    CROSS = "cross"


@dataclass
class TradingUniverseConfig:
    """پیکربندی Universe معاملاتی"""
    # 12 نماد ثابت
    symbols: List[str] = field(default_factory=lambda: [
        "BTC_USDT",
        "ETH_USDT",
        "XRP_USDT",
        "BNB_USDT",
        "SOL_USDT",
        "LINK_USDT",
        "UNI_USDT",
        "DOGE_USDT",
        "ADA_USDT",
        "HYPE_USDT",
        "ZEC_USDT",
        "SUI_USDT",
    ])
    
    # محدودیت‌های معاملاتی
    min_futures_volume_usdt: float = 1_000_000.0
    max_open_positions: int = 4
    max_position_per_symbol: int = 1
    position_equity_fraction: float = 0.25
    risk_per_trade: float = 0.01
    margin_mode: MarginMode = MarginMode.ISOLATED
    
    @property
    def position_risk_fraction(self) -> float:
        """ریسک نسبت به سرمایه تخصیص‌یافته = risk_per_trade / position_equity_fraction"""
        if self.position_equity_fraction > 0:
            return self.risk_per_trade / self.position_equity_fraction
        return 0.0
    
    def validate(self) -> List[str]:
        """اعتبارسنجی پیکربندی"""
        errors = []
        
        if len(self.symbols) != 12:
            errors.append(f"Symbol count must be 12, got {len(self.symbols)}")
        
        if len(set(self.symbols)) != len(self.symbols):
            errors.append("Duplicate symbols found")
        
        if self.min_futures_volume_usdt <= 0:
            errors.append("min_futures_volume_usdt must be > 0")
        
        if self.max_open_positions <= 0:
            errors.append("max_open_positions must be > 0")
        
        if self.max_position_per_symbol <= 0:
            errors.append("max_position_per_symbol must be > 0")
        
        if self.position_equity_fraction <= 0 or self.position_equity_fraction > 1:
            errors.append("position_equity_fraction must be in (0, 1]")
        
        if self.risk_per_trade <= 0 or self.risk_per_trade > 0.1:
            errors.append("risk_per_trade must be in (0, 0.1]")
        
        return errors
    
    def is_symbol_allowed(self, symbol: str) -> bool:
        """بررسی اینکه نماد در Universe مجاز است"""
        return symbol in self.symbols
    
    def get_symbol_count(self) -> int:
        """تعداد نمادها"""
        return len(self.symbols)


@dataclass
class VolumeFilterResult:
    """نتیجه فیلتر حجم"""
    symbol: str
    volume_usdt: float
    is_eligible: bool
    reason: Optional[str] = None


class VolumeFilter:
    """فیلتر حجم معاملاتی"""
    
    def __init__(self, min_volume_usdt: float = 1_000_000.0):
        self.min_volume_usdt = min_volume_usdt
    
    def check(self, symbol: str, volume_usdt: float) -> VolumeFilterResult:
        """بررسی حجم"""
        if volume_usdt >= self.min_volume_usdt:
            return VolumeFilterResult(symbol=symbol, volume_usdt=volume_usdt, is_eligible=True)
        else:
            return VolumeFilterResult(
                symbol=symbol,
                volume_usdt=volume_usdt,
                is_eligible=False,
                reason=f"Volume {volume_usdt:.2f} < minimum {self.min_volume_usdt:.2f}"
            )
