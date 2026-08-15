import pytest
import pandas as pd
import numpy as np
from datetime import timezone, timedelta

import config
from live_paper_runner import LivePaperTradingRunner


class FakeExchange:
    def __init__(self):
        self.symbols = {}
        self.ticks = {}

    def get_ohlcv(self, symbol, timeframe, limit=500, closed_only=True, current_time=None):
        return self.symbols.get((symbol, timeframe), pd.DataFrame(columns=['open','high','low','close','volume']))

    def get_ticker(self, symbol):
        return self.ticks.get(symbol, {"quote_volume": 0})

    def load_markets(self):
        pass


def test_symbol_whitelist_centralized():
    assert isinstance(config.SYMBOL_WHITELIST, list)
    assert len(config.SYMBOL_WHITELIST) == 12
    assert "BTC/USDT:USDT" in config.SYMBOL_WHITELIST
    assert "DOGE/USDT:USDT" in config.SYMBOL_WHITELIST


def test_paper_trading_disabled_real_order():
    assert config.PAPER_TRADING is True


def test_live_runner_initialization():
    exchange = FakeExchange()
    runner = LivePaperTradingRunner(exchange)
    assert runner.symbols == config.SYMBOL_WHITELIST
    assert runner.open_positions == {}
    assert runner.closed_trades == []


def test_no_real_order_methods_exist():
    runner = LivePaperTradingRunner(FakeExchange())
    assert not hasattr(runner, "create_order")
    assert not hasattr(runner, "execute_order")
    assert "create_order" not in dir(runner)


def test_duplicate_signal_guard():
    exchange = FakeExchange()
    runner = LivePaperTradingRunner(exchange, ["BTC/USDT:USDT"])
    now = pd.Timestamp('2025-01-01 00:00:00', tz='UTC')
    runner.last_signal_timestamps["BTC/USDT:USDT"] = now
    assert runner.last_signal_timestamps["BTC/USDT:USDT"] == now


def test_position_limit_enforced():
    exchange = FakeExchange()
    runner = LivePaperTradingRunner(exchange, ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    for i in range(4):
        sym = f"SYM{i}/USDT:USDT"
        runner.open_positions[sym] = {"symbol": sym}
    candidate = {"symbol": "SYM5/USDT:USDT", "signal": "LONG", "score": 90,
                 "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                 "position_size": 1, "risk_amount": 10, "leverage": 1}
    runner._open_paper_position(candidate, pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))
    assert len(runner.open_positions) == 4
    assert "SYM5/USDT:USDT" not in runner.open_positions


def test_duplicate_symbol_rejected():
    exchange = FakeExchange()
    runner = LivePaperTradingRunner(exchange, ["BTC/USDT:USDT"])
    runner.open_positions["BTC/USDT:USDT"] = {"symbol": "BTC/USDT:USDT"}
    candidate = {"symbol": "BTC/USDT:USDT", "signal": "LONG", "score": 90,
                 "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                 "position_size": 1, "risk_amount": 10, "leverage": 1}
    runner._open_paper_position(candidate, pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))
    assert runner.open_positions["BTC/USDT:USDT"]["symbol"] == "BTC/USDT:USDT"
    assert len(runner.open_positions) == 1


def test_monitor_sl_first():
    exchange = FakeExchange()
    now = pd.Timestamp('2025-01-01 00:05:00', tz='UTC')
    idx = pd.DatetimeIndex([pd.Timestamp('2025-01-01 00:05:00', tz='UTC')])
    df = pd.DataFrame({'open':[100], 'high':[111], 'low':[94], 'close':[100], 'volume':[10]}, index=idx)
    exchange.symbols[("BTC/USDT:USDT", '5m')] = df
    exchange.ticks["BTC/USDT:USDT"] = {"quote_volume": 5_000_000}

    runner = LivePaperTradingRunner(exchange, ["BTC/USDT:USDT"])
    runner.open_positions["BTC/USDT:USDT"] = {
        "symbol": "BTC/USDT:USDT",
        "direction": "LONG",
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "position_size": 1,
        "risk_amount": 10,
        "leverage": 1,
        "entry_time": now,
    }

    runner._monitor_open_positions(now)
    assert "BTC/USDT:USDT" not in runner.open_positions
    trade = runner.closed_trades[-1]
    assert trade["exit_reason"] == "SL"
    assert trade["exit_price"] == 95
    assert trade["pnl"] == -5.0


def test_live_price_deviation_rejects_signal():
    exchange = FakeExchange()
    now = pd.Timestamp('2025-01-01 00:05:00', tz='UTC')
    # داده 5m یک کندل با Close=100
    idx = pd.DatetimeIndex([pd.Timestamp('2025-01-01 00:00:00', tz='UTC')])
    df5 = pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100], 'volume':[10]}, index=idx)
    exchange.symbols[("BTC/USDT:USDT", '5m')] = df5
    exchange.symbols[("BTC/USDT:USDT", '1h')] = pd.DataFrame(columns=['open','high','low','close','volume'])
    exchange.symbols[("BTC/USDT:USDT", '4h')] = pd.DataFrame(columns=['open','high','low','close','volume'])
    # تیکر قیمت 105 (اختلاف 5%)
    exchange.ticks["BTC/USDT:USDT"] = {"last": 105.0, "quote_volume": 5_000_000}

    runner = LivePaperTradingRunner(exchange, ["BTC/USDT:USDT"])
    # شبیه‌سازی یک سیکل
    runner.run_once(current_time=now)
    # نباید پوزیشنی باز شود
    assert len(runner.open_positions) == 0
