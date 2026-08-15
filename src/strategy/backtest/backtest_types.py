# FILE: src/strategy/backtest/backtest_types.py

"""
تایپ‌های مخصوص Backtest Layer
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ExitReason(Enum):
    """دلایل خروج از پوزیشن"""
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    END_OF_DATA = "END_OF_DATA"


@dataclass
class BacktestConfig:
    """پیکربندی Backtest"""
    initial_equity: float = 10000.0
    allow_multiple_positions: bool = False
    same_candle_conflict_policy: str = "SL_FIRST"  # "SL_FIRST" or "TP_FIRST"
    commission: float = 0.0  # کارمزد (فعلاً صفر)
    slippage: float = 0.0  # لغزش (فعلاً صفر)
    
    def validate(self) -> List[str]:
        errors = []
        if self.initial_equity <= 0:
            errors.append("initial_equity must be > 0")
        if self.same_candle_conflict_policy not in ["SL_FIRST", "TP_FIRST"]:
            errors.append("same_candle_conflict_policy must be 'SL_FIRST' or 'TP_FIRST'")
        if self.commission < 0:
            errors.append("commission must be >= 0")
        if self.slippage < 0:
            errors.append("slippage must be >= 0")
        return errors


@dataclass
class PositionState:
    """وضعیت پوزیشن باز"""
    position_id: str
    signal_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    notional: float
    risk_amount: float
    entry_timestamp: int
    entry_index: int
    exit_timestamp: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    realized_pnl: float = 0.0
    is_open: bool = True


@dataclass
class TradeRecord:
    """رکورد یک معامله کامل"""
    trade_id: str
    signal_id: str
    symbol: str
    direction: str
    entry_timestamp: int
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    risk_amount: float
    exit_timestamp: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    realized_pnl: float = 0.0
    rr_realized: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'trade_id': self.trade_id,
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_timestamp': self.entry_timestamp,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'position_size': self.position_size,
            'risk_amount': self.risk_amount,
            'exit_timestamp': self.exit_timestamp,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason.value if self.exit_reason else None,
            'realized_pnl': self.realized_pnl,
            'rr_realized': self.rr_realized,
        }


@dataclass
class BacktestResult:
    """نتیجه کامل Backtest"""
    initial_equity: float
    final_equity: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    average_win: float
    average_loss: float
    average_rr: float
    trades: List[TradeRecord] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری"""
        return {
            'initial_equity': self.initial_equity,
            'final_equity': self.final_equity,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'gross_profit': self.gross_profit,
            'gross_loss': self.gross_loss,
            'net_profit': self.net_profit,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'average_win': self.average_win,
            'average_loss': self.average_loss,
            'average_rr': self.average_rr,
            'trades': [t.to_dict() for t in self.trades],
        }
