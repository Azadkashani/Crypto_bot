# FILE: src/strategy/risk/position_constraints.py

"""
محدودیت‌های پوزیشن و محاسبه اهرم دینامیک
"""

from dataclasses import dataclass
from typing import Optional, List
from ..config.trading_universe import TradingUniverseConfig, MarginMode


@dataclass
class PositionConstraintResult:
    """نتیجه بررسی محدودیت پوزیشن"""
    is_valid: bool
    rejection_reasons: List[str]
    position_margin: float = 0.0
    risk_amount: float = 0.0
    required_leverage: float = 0.0
    stop_distance_pct: float = 0.0


@dataclass
class LeverageConfig:
    """پیکربندی اهرم"""
    max_exchange_leverage: float = 100.0  # Gate.io حداکثر اهرم
    exchange_leverage_step: float = 1.0  # گام اهرم


class PositionConstraintEngine:
    """
    بررسی محدودیت‌های پوزیشن و محاسبه اهرم دینامیک
    """
    
    def __init__(
        self,
        universe_config: Optional[TradingUniverseConfig] = None,
        leverage_config: Optional[LeverageConfig] = None
    ):
        self.universe_config = universe_config or TradingUniverseConfig()
        self.leverage_config = leverage_config or LeverageConfig()
    
    def calculate_leverage(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str
    ) -> tuple[float, float]:
        """
        محاسبه اهرم دینامیک از فاصله Stop Loss
        
        Args:
            entry_price: قیمت ورود
            stop_loss: قیمت حد ضرر
            direction: "LONG" یا "SHORT"
        
        Returns:
            (stop_distance_pct, required_leverage)
        """
        if entry_price <= 0:
            raise ValueError(f"Invalid entry price: {entry_price}")
        
        if direction == "LONG":
            stop_distance = entry_price - stop_loss
        elif direction == "SHORT":
            stop_distance = stop_loss - entry_price
        else:
            raise ValueError(f"Invalid direction: {direction}")
        
        if stop_distance <= 0:
            raise ValueError(f"Invalid stop distance: {stop_distance}")
        
        stop_distance_pct = stop_distance / entry_price
        
        # اهرم = position_risk_fraction / stop_distance_pct
        position_risk_fraction = self.universe_config.position_risk_fraction
        
        if stop_distance_pct <= 0:
            raise ValueError("Stop distance percentage must be positive")
        
        required_leverage = position_risk_fraction / stop_distance_pct
        
        return stop_distance_pct, required_leverage
    
    def validate_position(
        self,
        symbol: str,
        volume_usdt: float,
        direction: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        open_positions_count: int,
        open_symbols: List[str],
        margin_mode: MarginMode = MarginMode.ISOLATED
    ) -> PositionConstraintResult:
        """
        بررسی کامل محدودیت‌های پوزیشن
        """
        reasons = []
        position_margin = 0.0
        risk_amount = 0.0
        required_leverage = 0.0
        stop_distance_pct = 0.0
        
        # ۱. بررسی Symbol
        if not self.universe_config.is_symbol_allowed(symbol):
            reasons.append(f"Symbol not in universe: {symbol}")
        
        # ۲. بررسی حجم
        if volume_usdt < self.universe_config.min_futures_volume_usdt:
            reasons.append(
                f"Volume {volume_usdt:.2f} < minimum {self.universe_config.min_futures_volume_usdt:.2f}"
            )
        
        # ۳. بررسی تعداد پوزیشن‌های باز
        if open_positions_count >= self.universe_config.max_open_positions:
            reasons.append(
                f"Max open positions reached: {open_positions_count} >= {self.universe_config.max_open_positions}"
            )
        
        # ۴. بررسی پوزیشن تکراری روی نماد
        if symbol in open_symbols:
            reasons.append(f"Position already open for symbol: {symbol}")
        
        # ۵. بررسی مارجین
        if margin_mode != MarginMode.ISOLATED:
            reasons.append(f"Margin mode must be ISOLATED, got {margin_mode.value}")
        
        # ۶. محاسبه تخصیص سرمایه
        position_margin = account_equity * self.universe_config.position_equity_fraction
        
        # ۷. محاسبه ریسک
        risk_amount = account_equity * self.universe_config.risk_per_trade
        
        # ۸. محاسبه اهرم
        try:
            stop_distance_pct, required_leverage = self.calculate_leverage(
                entry_price, stop_loss, direction
            )
            
            # ۹. بررسی سقف اهرم صرافی
            if required_leverage > self.leverage_config.max_exchange_leverage:
                reasons.append(
                    f"Required leverage {required_leverage:.2f}x exceeds max {self.leverage_config.max_exchange_leverage}x"
                )
        except ValueError as e:
            reasons.append(str(e))
        
        return PositionConstraintResult(
            is_valid=len(reasons) == 0,
            rejection_reasons=reasons,
            position_margin=position_margin,
            risk_amount=risk_amount,
            required_leverage=required_leverage,
            stop_distance_pct=stop_distance_pct,
        )
