import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta

import orchestrator
from orchestrator import MultiSymbolOrchestrator
import signal_scoring


def _make_ohlcv(rows=100, freq='5min', close=100.0):
    idx = pd.date_range(start='2025-01-01', periods=rows, freq=freq, tz='UTC')
    return pd.DataFrame({
        'open': close,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': 1000,
    }, index=idx)


class FakeExchange:
    def __init__(self):
        self.market_eligible = True
        self.volume = 5_000_000.0
        self.balance_total = 1000.0
        self.positions = []
        self.data = {}
        self.volume_sequence = []

    def is_market_eligible(self, symbol):
        if self.volume_sequence:
            volume = self.volume_sequence.pop(0)
        else:
            volume = self.volume
        return {"eligible": self.market_eligible, "volume_24h_usdt": volume}

    def get_balance(self):
        return {"currency": "USDT", "total": self.balance_total}

    def get_positions(self):
        return self.positions

    def get_ohlcv(self, symbol, timeframe, limit=500, closed_only=True, current_time=None):
        if symbol not in self.data:
            raise ValueError(f"No data for {symbol}")
        if timeframe not in self.data[symbol]:
            raise ValueError(f"No data for {symbol} {timeframe}")
        return self.data[symbol][timeframe]


class FakeExecutionEngine:
    def __init__(self):
        self.calls = []

    def execute(self, signal):
        self.calls.append(signal)
        return {"success": True, "executed": True}


@pytest.fixture
def fake_exchange():
    fe = FakeExchange()
    for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
        fe.data[sym] = {
            "4h": _make_ohlcv(100, '4h'),
            "1h": _make_ohlcv(100, '1h'),
            "5m": _make_ohlcv(100, '5min'),
        }
    return fe


def _make_signal(direction="LONG", volume=5_000_000.0):
    return {
        "signal": direction,
        "valid": True,
        "entry_price": 100.0,
        "stop_loss": 95.0 if direction == "LONG" else 105.0,
        "take_profit": 110.0 if direction == "LONG" else 90.0,
        "position_size": 2.0,
        "risk_amount": 10.0,
        "leverage": 10,
        "regime_4h": "BULLISH" if direction == "LONG" else "BEARISH",
        "regime_1h": "BULLISH" if direction == "LONG" else "BEARISH",
        "rsi_recovery": True,
        "choch": True,
        "bos": True,
        "risk_reward": 2.0,
        "volume_24h_usdt": volume,
    }


@pytest.fixture
def patch_strategy(monkeypatch):
    def _patch(mapping):
        def fake_generate_signal(df_4h, df_1h, df_5m, as_of=None, account_balance=None, symbol=None):
            if symbol in mapping:
                return mapping[symbol]
            return mapping.get("default", {"signal": "NONE", "valid": False})
        monkeypatch.setattr(orchestrator.strategy, "generate_signal", fake_generate_signal)
    return _patch


def test_no_valid_signals(fake_exchange, patch_strategy):
    patch_strategy({"default": {"signal": "NONE", "valid": False}})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert result["candidates_count"] == 0


def test_one_valid_signal(fake_exchange, patch_strategy):
    sig = _make_signal("LONG")
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "LONG"
    assert result["symbol"] == "BTC/USDT:USDT"
    assert result["candidates_count"] == 1


def test_multiple_signals_are_ranked(fake_exchange, patch_strategy):
    sig_btc = _make_signal("LONG", volume=2_000_000.0)
    sig_eth = _make_signal("LONG", volume=5_000_000.0)
    sig_sol = _make_signal("LONG", volume=3_000_000.0)
    patch_strategy({
        "BTC/USDT:USDT": sig_btc,
        "ETH/USDT:USDT": sig_eth,
        "SOL/USDT:USDT": sig_sol,
    })
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    assert result["signal"] == "LONG"
    assert result["symbol"] == "ETH/USDT:USDT"


def test_best_signal_selected(fake_exchange, patch_strategy):
    sig_btc = _make_signal("LONG", volume=2_000_000.0)
    sig_eth = _make_signal("LONG", volume=8_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig_btc, "ETH/USDT:USDT": sig_eth})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT", "ETH/USDT:USDT"])
    assert result["symbol"] == "ETH/USDT:USDT"


def test_tie_score_uses_tie_break(fake_exchange, patch_strategy):
    sig_aaa = _make_signal("LONG", volume=2_000_000.0)
    sig_bbb = _make_signal("LONG", volume=2_000_000.0)
    fake_exchange.data["AAA/USDT:USDT"] = fake_exchange.data["BTC/USDT:USDT"]
    fake_exchange.data["BBB/USDT:USDT"] = fake_exchange.data["BTC/USDT:USDT"]
    patch_strategy({"AAA/USDT:USDT": sig_aaa, "BBB/USDT:USDT": sig_bbb})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["AAA/USDT:USDT", "BBB/USDT:USDT"])
    assert result["symbol"] == "AAA/USDT:USDT"


def test_volume_below_1m_rejected(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=999_999.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    fake_exchange.volume = 999_999.0
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 0
    assert result["signal"] == "NONE"


def test_volume_exactly_one_million_allowed(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=1_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    fake_exchange.volume = 1_000_000.0
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 1


def test_volume_above_one_million_allowed(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=1_500_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    fake_exchange.volume = 1_500_000.0
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 1


def test_non_perpetual_rejected(fake_exchange, patch_strategy):
    fake_exchange.market_eligible = False
    sig = _make_signal("LONG")
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 0


def test_wrong_settlement_rejected(fake_exchange, patch_strategy):
    fake_exchange.market_eligible = False
    sig = _make_signal("LONG")
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 0


def test_live_trading_disabled_no_order(fake_exchange, patch_strategy):
    sig = _make_signal("LONG")
    patch_strategy({"BTC/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=False)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Live trading disabled" in result["reason"]
    assert exec_engine.calls == []


def test_balance_insufficient_during_final_recheck(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    fake_exchange.balance_total = 1.0
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Insufficient balance" in result["reason"]
    assert exec_engine.calls == []


def test_position_appears_during_final_recheck(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    fake_exchange.positions = [{"symbol": "BTC/USDT:USDT", "contracts": 0.5, "side": "long"}]
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Existing position" in result["reason"]
    assert exec_engine.calls == []


def test_volume_drops_below_1m_before_execution(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)

    # ابتدا حجم بالا برای اسکن موفق، سپس در safety recheck حجم کم
    fake_exchange.volume_sequence = [2_000_000.0, 900_000.0]
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Volume below minimum" in result["reason"]
    assert exec_engine.calls == []


def test_duplicate_signal_only_one_execution(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)

    first = orch.run(["BTC/USDT:USDT"])
    second = orch.run(["BTC/USDT:USDT"])

    assert first["signal"] == "LONG"
    assert second["signal"] == "NONE"
    assert "Duplicate" in second["reason"]
    assert len(exec_engine.calls) == 1


def test_one_symbol_throws_exception_others_continue(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    fake_exchange.data["GOOD/USDT:USDT"] = fake_exchange.data["BTC/USDT:USDT"]
    patch_strategy({"GOOD/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BAD/USDT:USDT", "GOOD/USDT:USDT"])
    assert result["candidates_count"] == 1
    assert result["symbol"] == "GOOD/USDT:USDT"


def test_invalid_signal_not_scored(fake_exchange, patch_strategy):
    invalid = _make_signal("LONG")
    invalid["valid"] = False
    patch_strategy({"BTC/USDT:USDT": invalid})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["candidates_count"] == 0
    assert exec_engine.calls == []


def test_best_candidate_fails_safety_no_fallback(fake_exchange, patch_strategy):
    sig_btc = _make_signal("LONG", volume=5_000_000.0)
    sig_eth = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig_btc, "ETH/USDT:USDT": sig_eth})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    fake_exchange.balance_total = 1.0
    result = orch.run(["BTC/USDT:USDT", "ETH/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Insufficient balance" in result["reason"]
    assert exec_engine.calls == []


def test_live_disabled_with_valid_signal_no_order(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=False)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Live trading disabled" in result["reason"]
    assert exec_engine.calls == []


def test_no_api_credentials_no_real_order(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    def raise_perm(*args, **kwargs):
        raise PermissionError("Private data requires API credentials")
    fake_exchange.get_balance = raise_perm
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    assert result["signal"] == "NONE"
    assert "Balance unavailable" in result["reason"]
    assert exec_engine.calls == []


def test_deterministic_execution(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=False)

    r1 = orch.run(["BTC/USDT:USDT"])
    r2 = orch.run(["BTC/USDT:USDT"])

    assert r1["signal"] == r2["signal"]
    assert r1["symbol"] == r2["symbol"]
    assert r1["score"] == r2["score"]


def test_no_cross_timeframe_data_leakage(fake_exchange, patch_strategy):
    calls = []
    original_get_ohlcv = fake_exchange.get_ohlcv

    def tracking_get_ohlcv(symbol, timeframe, *args, **kwargs):
        calls.append((symbol, timeframe))
        return original_get_ohlcv(symbol, timeframe, *args, **kwargs)

    fake_exchange.get_ohlcv = tracking_get_ohlcv
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    orch.run(["BTC/USDT:USDT"])
    assert ("BTC/USDT:USDT", "4h") in calls
    assert ("BTC/USDT:USDT", "1h") in calls
    assert ("BTC/USDT:USDT", "5m") in calls


def test_no_future_candle_usage(fake_exchange, patch_strategy):
    as_of = pd.Timestamp('2025-01-01 00:00:00', tz='UTC')
    received = {}
    original_get_ohlcv = fake_exchange.get_ohlcv

    def tracking_get_ohlcv(symbol, timeframe, limit=500, closed_only=True, current_time=None):
        received[(symbol, timeframe)] = current_time
        return original_get_ohlcv(symbol, timeframe, limit, closed_only, current_time)

    fake_exchange.get_ohlcv = tracking_get_ohlcv
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    orch.run(["BTC/USDT:USDT"], as_of=as_of)
    assert received[("BTC/USDT:USDT", "5m")] == as_of


def test_only_best_signal_passed_to_execution(fake_exchange, patch_strategy):
    sig_btc = _make_signal("LONG", volume=2_000_000.0)
    sig_eth = _make_signal("LONG", volume=5_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig_btc, "ETH/USDT:USDT": sig_eth})
    exec_engine = FakeExecutionEngine()
    orch = MultiSymbolOrchestrator(fake_exchange, exec_engine, live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT", "ETH/USDT:USDT"])
    assert result["symbol"] == "ETH/USDT:USDT"
    assert len(exec_engine.calls) == 1
    assert exec_engine.calls[0]["symbol"] == "ETH/USDT:USDT"


def test_candidate_count_correct(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({
        "BTC/USDT:USDT": sig,
        "ETH/USDT:USDT": sig,
        "SOL/USDT:USDT": sig,
    })
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"])
    assert result["candidates_count"] == 3


def test_result_structure(fake_exchange, patch_strategy):
    sig = _make_signal("LONG", volume=2_000_000.0)
    patch_strategy({"BTC/USDT:USDT": sig})
    orch = MultiSymbolOrchestrator(fake_exchange, FakeExecutionEngine(), live_trading_enabled=True)
    result = orch.run(["BTC/USDT:USDT"])
    for key in ["success", "signal", "symbol", "score", "reason", "candidates_count", "candidates"]:
        assert key in result
    assert isinstance(result["candidates"], list)
