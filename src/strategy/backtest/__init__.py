# FILE: src/strategy/backtest/__init__.py

"""
Backtest & Simulation Layer — شبیه‌سازی تاریخی معاملات
"""

from .backtest_types import (
    BacktestConfig,
    BacktestResult,
    TradeRecord,
    PositionState,
    ExitReason
)
from .backtest_engine import BacktestEngine

__all__ = [
    'BacktestConfig',
    'BacktestResult',
    'TradeRecord',
    'PositionState',
    'ExitReason',
    'BacktestEngine'
]
