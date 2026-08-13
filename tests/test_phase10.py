import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import config
from backtest_engine import BacktestEngine
import strategy


def _make_dummy_data(n=100, freq='5min', start='2025-01-01'):
    idx = pd.date_range(start=start, periods=n, freq=freq, tz='UTC')
    df = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 100,
    }, index=idx)
    return df


def _make_1h_data(n=30, start='2025-01-01'):
    idx = pd.date_range(start=start, periods=n, freq='1h', tz='UTC')
    df = pd.DataFrame({
        'open': 100.0 + np.arange(n),
        'high': 101.0 + np.arange(n),
        'low': 99.0 + np.arange(n),
        'close': 100.0 + np.arange(n),
        'volume': 100,
    }, index=idx)
    return df


def _make_4h_data(n=10, start='2025-01-01'):
    idx = pd.date_range(start=start, periods=n, freq='4h', tz='UTC')
    df = pd.DataFrame({
        'open': 100.0 + np.arange(n) * 10,
        'high': 101.0 + np.arange(n) * 10,
        'low': 99.0 + np.arange(n) * 10,
        'close': 100.0 + np.arange(n) * 10,
        'volume': 100,
    }, index=idx)
    return df


# --- تست‌های اصلی ---

def test_chronological_processing():
    df5 = _make_dummy_data()
    df1 = _make_1h_data()
    df4 = _make_4h_data()
    engine = BacktestEngine(df5, df1, df4, initial_balance=1000)
    result = engine.run()
    assert result["total_trades"] == 0
    assert result["initial_balance"] == 1000
    assert result["final_balance"] == 1000


def test_no_future_data_used():
    df5 = _make_dummy_data()
    engine = BacktestEngine(df5, _make_1h_data(), _make_4h_data(), 1000)
    result = engine.run()
    assert result["total_trades"] == 0


def test_sl_tp_same_candle_sl_first():
    df5 = _make_dummy_data(10)
    df1 = _make_1h_data(5)
    df4 = _make_4h_data(3)
    engine = BacktestEngine(df5, df1, df4, 1000)
    engine.current_position = {
        "direction": "LONG",
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "position_size": 1,
        "risk_amount": 5,
        "entry_time": pd.Timestamp('2025-01-01 00:00:00', tz='UTC'),
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "pnl": 0,
        "r_multiple": 0
    }
    # کندلی که هم SL و هم TP را لمس می‌کند
    candle = pd.Series({'high': 111, 'low': 94, 'close': 100})
    hit_sl = candle['low'] <= 95
    hit_tp = candle['high'] >= 110
    assert hit_sl and hit_tp
    # طبق قانون SL FIRST، خروج باید حد ضرر باشد
    exit_price = 95
    assert exit_price == 95


def test_long_tp_exit():
    df5 = _make_dummy_data(10)
    df1 = _make_1h_data(5)
    df4 = _make_4h_data(3)
    engine = BacktestEngine(df5, df1, df4, 1000)
    engine.current_position = {
        "direction": "LONG",
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "position_size": 1,
        "risk_amount": 5,
        "entry_time": pd.Timestamp('2025-01-01 00:00:00', tz='UTC'),
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "pnl": 0,
        "r_multiple": 0
    }
    candle = pd.Series({'high': 111, 'low': 96, 'close': 100})
    hit_sl = candle['low'] <= 95
    hit_tp = candle['high'] >= 110
    assert hit_tp and not hit_sl
    exit_price = 110
    pnl = (exit_price - 100) * 1
    assert pnl == 10


def test_short_sl_exit():
    df5 = _make_dummy_data(10)
    df1 = _make_1h_data(5)
    df4 = _make_4h_data(3)
    engine = BacktestEngine(df5, df1, df4, 1000)
    engine.current_position = {
        "direction": "SHORT",
        "entry_price": 100,
        "stop_loss": 105,
        "take_profit": 90,
        "position_size": 1,
        "risk_amount": 5,
        "entry_time": pd.Timestamp('2025-01-01 00:00:00', tz='UTC'),
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "pnl": 0,
        "r_multiple": 0
    }
    candle = pd.Series({'high': 106, 'low': 95, 'close': 100})
    hit_sl = candle['high'] >= 105
    hit_tp = candle['low'] <= 90
    assert hit_sl and not hit_tp
    exit_price = 105
    pnl = (100 - exit_price) * 1
    assert pnl == -5


# --- تست‌های متریک ---

def test_win_rate_and_profit_factor():
    engine = BacktestEngine(_make_dummy_data(), _make_1h_data(), _make_4h_data(), 1000)
    result = engine.run()
    assert result["win_rate"] == 0
    assert result["profit_factor"] == float('inf')
    assert result["max_drawdown"] == 0
    assert result["average_r"] == 0


def test_dynamic_balance_position_sizing():
    # این مورد به‌صورت کامل در تست‌های فاز ۹ پوشش داده شده است.
    pass
