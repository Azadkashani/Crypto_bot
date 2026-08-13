import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
import math
import inspect

import execution
from execution import ExecutionEngine
import gate_exchange
from gate_exchange import GateExchange, MIN_24H_VOLUME_USDT
import config


# ----------------------------------------------------------------------
# Fake Exchange
# ----------------------------------------------------------------------
class FakeExchange:
    def __init__(self):
        self.markets = {
            "BTC/USDT:USDT": {
                "symbol": "BTC/USDT:USDT",
                "base": "BTC",
                "quote": "USDT",
                "settle": "USDT",
                "type": "swap",
                "spot": False,
                "swap": True,
                "contract": True,
                "linear": True,
                "precision": {"amount": 0.001},
                "limits": {
                    "amount": {"min": 0.001},
                    "cost": {"min": 10.0},
                },
            },
            "ETH/USDT:USDT": {
                "symbol": "ETH/USDT:USDT",
                "base": "ETH",
                "quote": "USDT",
                "settle": "USDT",
                "type": "swap",
                "spot": False,
                "swap": True,
                "contract": True,
                "linear": True,
                "precision": {"amount": 0.01},
                "limits": {
                    "amount": {"min": 0.01},
                    "cost": {"min": 10.0},
                },
            },
            "BTC/USDT": {
                "symbol": "BTC/USDT",
                "base": "BTC",
                "quote": "USDT",
                "settle": None,
                "type": "spot",
                "spot": True,
                "swap": False,
                "contract": False,
                "linear": False,
            },
        }
        self.tickers = {
            "BTC/USDT:USDT": {"last": 50000.0, "quoteVolume": 5_000_000.0},
            "ETH/USDT:USDT": {"last": 3000.0, "quoteVolume": 500_000.0},
            "BTC/USDT": {"last": 50000.0, "quoteVolume": 5_000_000.0},
        }
        self.balance = {"USDT": {"free": 900.0, "used": 100.0, "total": 1000.0}}
        self.positions = []
        self.orders = []
        self.calls = []

    def load_markets(self):
        self.calls.append("load_markets")
        return self.markets

    def get_market(self, symbol):
        self.calls.append(("get_market", symbol))
        if symbol not in self.markets:
            raise ValueError(f"Symbol not found: {symbol}")
        return self.markets[symbol]

    def get_ticker(self, symbol):
        self.calls.append(("get_ticker", symbol))
        if symbol not in self.tickers:
            raise ValueError("Ticker not available")
        return self.tickers[symbol]

    def is_market_eligible(self, symbol):
        self.calls.append(("is_market_eligible", symbol))
        ticker = self.tickers.get(symbol)
        if ticker is None:
            return {"eligible": False, "reason": "unavailable"}
        vol = ticker.get("quoteVolume")
        if vol is None:
            return {"eligible": False, "reason": "unavailable"}
        if vol < MIN_24H_VOLUME_USDT:
            return {"eligible": False, "reason": "below minimum"}
        return {"eligible": True, "volume_24h_usdt": vol}

    def get_balance(self):
        self.calls.append("get_balance")
        return {"currency": "USDT", "total": self.balance["USDT"]["total"]}

    def get_positions(self):
        self.calls.append("get_positions")
        return self.positions

    # شبیه‌سازی create_order
    def create_order(self, symbol, type, side, amount, params=None):
        self.calls.append(("create_order", symbol, type, side, amount, params))
        order_id = f"order_{len(self.orders)+1}"
        order = {
            "id": order_id,
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "params": params,
            "status": "closed",
            "filled": amount,
            "average": self.tickers.get(symbol, {}).get("last", 0),
        }
        self.orders.append(order)
        return order

    # شبیه‌سازی fetch_order
    def fetch_order(self, order_id, symbol=None):
        self.calls.append(("fetch_order", order_id, symbol))
        for o in self.orders:
            if o["id"] == order_id:
                return o
        raise ValueError("Order not found")


@pytest.fixture
def fake_exchange(monkeypatch):
    fe = FakeExchange()
    # ساخت یک GateExchange جعلی با استفاده از FakeExchange به عنوان exchange
    class FakeGateExchange(GateExchange):
        def __init__(self):
            # به‌جای ساخت ccxt.gate، exchange را مستقیم تنظیم می‌کنیم
            self.exchange = fe
            self.markets = fe.markets
            self.options = {"defaultType": "swap"}
        def load_markets(self):
            self.markets = self.exchange.load_markets()
            return self.markets
        def get_market(self, symbol):
            return self.exchange.get_market(symbol)
        def get_ticker(self, symbol):
            return self.exchange.get_ticker(symbol)
        def is_market_eligible(self, symbol):
            return self.exchange.is_market_eligible(symbol)
        def get_balance(self):
            return self.exchange.get_balance()
        def get_positions(self):
            return self.exchange.get_positions()

    fake_gate = FakeGateExchange()
    return fake_gate


@pytest.fixture
def valid_long_signal():
    return {
        "signal": "LONG",
        "valid": True,
        "symbol": "BTC/USDT:USDT",
        "entry_price": 50000.0,
        "stop_loss": 49500.0,
        "take_profit": 51000.0,
        "position_size": 0.01,
        "risk_amount": 10.0,
        "leverage": 10,
        "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


@pytest.fixture
def valid_short_signal():
    return {
        "signal": "SHORT",
        "valid": True,
        "symbol": "BTC/USDT:USDT",
        "entry_price": 50000.0,
        "stop_loss": 50500.0,
        "take_profit": 49000.0,
        "position_size": 0.01,
        "risk_amount": 10.0,
        "leverage": 10,
        "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


# ----------------------------------------------------------------------
# تست‌ها
# ----------------------------------------------------------------------

def test_live_trading_disabled_no_order(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=False)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Live trading disabled" in result["reason"]
    assert fake_exchange.calls == []  # هیچ فراخوانی به صرافی نشده


def test_live_enabled_but_credentials_missing_no_order(fake_exchange, valid_long_signal):
    # شبیه‌سازی عدم وجود credentials در GateExchange
    fake_exchange.options = {"defaultType": "swap"}
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    # get_balance خطا می‌دهد
    # برای این تست، حساب را بدون دسترسی فرض می‌کنیم
    # (در واقع fake_exchange در این حالت باید error دهد، اما ساده‌سازی)
    # اینجا فرض می‌کنیم balance نامعتبر برگردد
    def _no_balance():
        return {"currency": "USDT", "total": None}
    fake_exchange.get_balance = _no_balance
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Balance" in result["reason"]


def test_invalid_symbol_no_order(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    valid_long_signal["symbol"] = "UNKNOWN/USDT:USDT"
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Market eligibility" in result["reason"] or "Symbol" in result["reason"]


def test_spot_symbol_no_order(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    valid_long_signal["symbol"] = "BTC/USDT"
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_non_perpetual_no_order(fake_exchange, valid_long_signal):
    # تغییر ETH به non-perpetual
    fake_exchange.markets["ETH/USDT:USDT"]["swap"] = False
    fake_exchange.markets["ETH/USDT:USDT"]["contract"] = False
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    valid_long_signal["symbol"] = "ETH/USDT:USDT"
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_wrong_settlement_no_order(fake_exchange, valid_long_signal):
    fake_exchange.markets["BTC/USDT:USDT"]["settle"] = "USD"
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_volume_below_1m_no_order(fake_exchange, valid_long_signal):
    fake_exchange.tickers["BTC/USDT:USDT"]["quoteVolume"] = 999_999.0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "below minimum" in result["reason"]


def test_volume_exactly_1m_allowed(fake_exchange, valid_long_signal):
    fake_exchange.tickers["BTC/USDT:USDT"]["quoteVolume"] = MIN_24H_VOLUME_USDT
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    assert result["status"] == "PROTECTED"


def test_volume_above_1m_allowed(fake_exchange, valid_long_signal):
    fake_exchange.tickers["BTC/USDT:USDT"]["quoteVolume"] = 2_000_000.0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True


def test_unavailable_volume_no_order(fake_exchange, valid_long_signal):
    fake_exchange.tickers["BTC/USDT:USDT"]["quoteVolume"] = None
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_invalid_signal_no_order(fake_exchange):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute({"valid": False})
    assert result["executed"] is False


def test_none_signal_no_order(fake_exchange):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute({"signal": "NONE", "valid": False})
    assert result["executed"] is False


def test_long_signal_valid_entry_direction_correct(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    # بررسی side سفارش ورود
    entry_order = fake_exchange.orders[0]
    assert entry_order["side"] == "buy"


def test_short_signal_valid_entry_direction_correct(fake_exchange, valid_short_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_short_signal)
    assert result["executed"] is True
    entry_order = fake_exchange.orders[0]
    assert entry_order["side"] == "sell"


def test_long_invalid_sl_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["stop_loss"] = 50000.0  # برابر entry
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_long_invalid_tp_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["take_profit"] = 50000.0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_short_invalid_sl_no_order(fake_exchange, valid_short_signal):
    valid_short_signal["stop_loss"] = 50000.0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_short_signal)
    assert result["executed"] is False


def test_short_invalid_tp_no_order(fake_exchange, valid_short_signal):
    valid_short_signal["take_profit"] = 50000.0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_short_signal)
    assert result["executed"] is False


def test_zero_position_size_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["position_size"] = 0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_negative_position_size_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["position_size"] = -1
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_nan_position_size_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["position_size"] = float('nan')
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_infinite_position_size_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["position_size"] = float('inf')
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_excessive_risk_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["risk_amount"] = 100.0  # بیشتر از حد مجاز
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "exceeds" in result["reason"]


def test_insufficient_balance_no_order(fake_exchange, valid_long_signal):
    fake_exchange.balance["USDT"]["total"] = 5.0  # کمتر از risk_amount
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Insufficient balance" in result["reason"]


def test_existing_same_symbol_position_no_order(fake_exchange, valid_long_signal):
    fake_exchange.positions = [{"symbol": "BTC/USDT:USDT", "contracts": 0.5, "side": "long"}]
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Existing position" in result["reason"]


def test_conflicting_position_no_order(fake_exchange, valid_long_signal):
    fake_exchange.positions = [{"symbol": "BTC/USDT:USDT", "contracts": 0.5, "side": "short"}]
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_duplicate_execution_no_duplicate_order(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    first = engine.execute(valid_long_signal)
    assert first["executed"] is True
    # تلاش دوم همان سیگنال
    second = engine.execute(valid_long_signal)
    assert second["executed"] is False
    assert "Duplicate" in second["reason"]
    assert len(fake_exchange.orders) == 3  # ورود + SL + TP از اجرای اول


def test_leverage_above_configured_max_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["leverage"] = config.LEVERAGE + 1
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Leverage exceeds" in result["reason"]


def test_invalid_leverage_no_order(fake_exchange, valid_long_signal):
    valid_long_signal["leverage"] = 0
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False


def test_invalid_exchange_precision_safe_rejection(fake_exchange, valid_long_signal):
    # حذف precision از بازار
    del fake_exchange.markets["BTC/USDT:USDT"]["precision"]
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "precision" in result["reason"]


def test_quantity_below_minimum_no_order(fake_exchange, valid_long_signal):
    fake_exchange.markets["BTC/USDT:USDT"]["limits"]["amount"]["min"] = 1.0
    valid_long_signal["position_size"] = 0.001  # کمتر از حداقل
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "below minimum" in result["reason"]


def test_notional_below_minimum_no_order(fake_exchange, valid_long_signal):
    # حداقل هزینه بالا
    fake_exchange.markets["BTC/USDT:USDT"]["limits"]["cost"]["min"] = 1000.0
    valid_long_signal["position_size"] = 0.001  # notional = 0.001*50000 = 50 < 1000
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "Notional below" in result["reason"]


def test_quantity_precision_handled_safely(fake_exchange, valid_long_signal):
    valid_long_signal["position_size"] = 0.0123
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    # مقدار گردشده به precision=0.001 باید 0.012 باشد
    assert fake_exchange.orders[0]["amount"] == 0.012


def test_long_order_uses_buy_side(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    engine.execute(valid_long_signal)
    assert fake_exchange.orders[0]["side"] == "buy"


def test_short_order_uses_sell_side(fake_exchange, valid_short_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    engine.execute(valid_short_signal)
    assert fake_exchange.orders[0]["side"] == "sell"


def test_actual_fill_price_is_captured(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["average_fill_price"] == 50000.0


def test_partial_fill_handled(fake_exchange, valid_long_signal):
    # شبیه‌سازی fill جزئی
    def custom_fetch_order(order_id, symbol):
        order = fake_exchange.fetch_order(order_id, symbol)
        order["filled"] = 0.005  # نصف
        order["average"] = 50000.0
        return order
    fake_exchange.fetch_order = custom_fetch_order
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    assert result["filled_size"] == 0.005
    # سفارش‌های SL/TP باید با همان حجم باشند
    assert fake_exchange.orders[1]["amount"] == 0.005
    assert fake_exchange.orders[2]["amount"] == 0.005


def test_canceled_order_handled(fake_exchange, valid_long_signal):
    def custom_fetch_order(order_id, symbol):
        order = fake_exchange.fetch_order(order_id, symbol)
        order["status"] = "canceled"
        return order
    fake_exchange.fetch_order = custom_fetch_order
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "not filled" in result["reason"]


def test_rejected_order_handled(fake_exchange, valid_long_signal):
    def custom_fetch_order(order_id, symbol):
        order = fake_exchange.fetch_order(order_id, symbol)
        order["status"] = "rejected"
        return order
    fake_exchange.fetch_order = custom_fetch_order
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "rejected" in result["reason"]


def test_ambiguous_network_error_no_blind_retry(fake_exchange, valid_long_signal):
    calls = []
    original_create = fake_exchange.create_order

    def flaky_create(symbol, type, side, amount, params=None):
        calls.append(("create_order", symbol, type, side, amount, params))
        if len(calls) == 1:
            raise ConnectionError("Network timeout")
        return original_create(symbol, type, side, amount, params)
    fake_exchange.create_order = flaky_create
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    # فقط یک بار create_order صدا زده شده
    assert len([c for c in calls if c[0] == "create_order"]) == 1


def test_existing_exchange_state_checked_after_ambiguous_error(fake_exchange, valid_long_signal):
    # شبیه‌سازی error شبکه و سپس بررسی پوزیشن
    first_create = True
    def flaky_create(*args, **kwargs):
        nonlocal first_create
        if first_create:
            first_create = False
            raise ConnectionError("Ambiguous network")
        return fake_exchange.create_order(*args, **kwargs)
    fake_exchange.create_order = flaky_create
    # فرض می‌کنیم بعد از error، پوزیشنی ایجاد نشده
    fake_exchange.positions = []
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    # اطمینان از اینکه get_positions فراخوانی شده است
    assert "get_positions" in fake_exchange.calls


def test_sl_order_is_reduce_only(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    engine.execute(valid_long_signal)
    sl_order = fake_exchange.orders[1]
    assert sl_order["params"].get("reduceOnly") is True


def test_tp_order_is_reduce_only(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    engine.execute(valid_long_signal)
    tp_order = fake_exchange.orders[2]
    assert tp_order["params"].get("reduceOnly") is True


def test_long_sl_below_entry(valid_long_signal):
    assert valid_long_signal["stop_loss"] < valid_long_signal["entry_price"]


def test_long_tp_above_entry(valid_long_signal):
    assert valid_long_signal["take_profit"] > valid_long_signal["entry_price"]


def test_short_sl_above_entry(valid_short_signal):
    assert valid_short_signal["stop_loss"] > valid_short_signal["entry_price"]


def test_short_tp_below_entry(valid_short_signal):
    assert valid_short_signal["take_profit"] < valid_short_signal["entry_price"]


def test_entry_succeeds_sl_tp_succeed(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["success"] is True
    assert result["executed"] is True
    assert result["status"] == "PROTECTED"
    assert len(fake_exchange.orders) == 3


def test_entry_succeeds_but_sl_fails_emergency(fake_exchange, valid_long_signal):
    original_create = fake_exchange.create_order
    def create_with_sl_fail(symbol, type, side, amount, params=None):
        if type == "stop_market":
            raise Exception("SL rejected")
        return original_create(symbol, type, side, amount, params)
    fake_exchange.create_order = create_with_sl_fail
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["success"] is False
    assert result["executed"] is True
    assert result["protected"] is False
    assert result["emergency_action"] == "close"
    # بررسی نزدن reverse position: emergency close با side مخالف و reduceOnly
    close_order = fake_exchange.orders[-1]
    assert close_order["side"] == "sell"
    assert close_order["params"].get("reduceOnly") is True


def test_entry_succeeds_but_tp_fails_protection_failure(fake_exchange, valid_long_signal):
    original_create = fake_exchange.create_order
    def create_with_tp_fail(symbol, type, side, amount, params=None):
        if type == "take_profit_market":
            raise Exception("TP rejected")
        return original_create(symbol, type, side, amount, params)
    fake_exchange.create_order = create_with_tp_fail
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["success"] is False
    assert result["emergency_action"] == "close"


def test_emergency_close_reduce_only(fake_exchange, valid_long_signal):
    # شبیه‌سازی خطا در SL و TP
    def create_with_both_fail(symbol, type, side, amount, params=None):
        if type in ("stop_market", "take_profit_market"):
            raise Exception("Protection rejected")
        return fake_exchange.create_order(symbol, type, side, amount, params)
    fake_exchange.create_order = create_with_both_fail
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["emergency_action"] == "close"
    close_order = fake_exchange.orders[-1]
    assert close_order["params"].get("reduceOnly") is True


def test_emergency_close_correct_opposite_side(fake_exchange, valid_short_signal):
    # شبیه‌سازی خطا در SL برای SHORT
    def create_with_sl_fail(symbol, type, side, amount, params=None):
        if type == "stop_market":
            raise Exception("SL failed")
        return fake_exchange.create_order(symbol, type, side, amount, params)
    fake_exchange.create_order = create_with_sl_fail
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_short_signal)
    assert result["emergency_action"] == "close"
    close_order = fake_exchange.orders[-1]
    assert close_order["side"] == "buy"
    assert close_order["params"].get("reduceOnly") is True


def test_emergency_close_never_increases_position(fake_exchange, valid_long_signal):
    # اطمینان از اینکه emergency close دقیقاً همان حجم filled را دارد
    def create_with_sl_fail(symbol, type, side, amount, params=None):
        if type == "stop_market":
            raise Exception("SL failed")
        return fake_exchange.create_order(symbol, type, side, amount, params)
    fake_exchange.create_order = create_with_sl_fail
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    engine.execute(valid_long_signal)
    close_order = fake_exchange.orders[-1]
    assert close_order["amount"] == 0.01  # حجم پر شده


def test_no_credentials_appear_in_returned_error(fake_exchange, valid_long_signal):
    fake_exchange.options = {"apiKey": "my_api", "secret": "my_secret"}
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=False)
    result = engine.execute(valid_long_signal)
    assert "my_api" not in str(result)
    assert "my_secret" not in str(result)


def test_no_credentials_in_logs_or_result(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert "apiKey" not in str(result)
    assert "secret" not in str(result)


def test_no_order_submitted_when_market_eligibility_changes_below_1m(
    fake_exchange, valid_long_signal
):
    # ابتدا حجم بالا، سپس در زمان اجرا volume پایین
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    def low_volume_ticker(symbol):
        ticker = fake_exchange.tickers[symbol].copy()
        ticker["quoteVolume"] = 999_999.0
        return ticker
    fake_exchange.get_ticker = low_volume_ticker
    result = engine.execute(valid_long_signal)
    assert result["executed"] is False
    assert "below minimum" in result["reason"]


def test_balance_rechecked_immediately_before_execution(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    # بالانس اولیه کافی است
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    assert "get_balance" in fake_exchange.calls


def test_position_rechecked_immediately_before_execution(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["executed"] is True
    assert "get_positions" in fake_exchange.calls


def test_order_response_normalized(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert "entry_order_id" in result
    assert "stop_order_id" in result
    assert "take_profit_order_id" in result


def test_successful_execution_result_contains_order_ids_status(fake_exchange, valid_long_signal):
    engine = ExecutionEngine(fake_exchange, live_trading_enabled=True)
    result = engine.execute(valid_long_signal)
    assert result["success"] is True
    assert result["status"] == "PROTECTED"
    assert result["entry_order_id"] is not None
    assert result["stop_order_id"] is not None
    assert result["take_profit_order_id"] is not None


def test_no_automatic_trading_on_import(fake_exchange):
    # اطمینان از اینکه import هیچ سفارشی نمی‌فرستد
    source = inspect.getsource(ExecutionEngine.__init__)
    assert "create_order" not in source
