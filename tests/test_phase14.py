import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
import inspect

import gate_exchange
from gate_exchange import GateExchange, MIN_24H_VOLUME_USDT, SUPPORTED_TIMEFRAMES


# ---------- Fake Exchange ----------

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
            "XRP/USDT:USDT": {
                "symbol": "XRP/USDT:USDT",
                "base": "XRP",
                "quote": "USDT",
                "settle": "USDT",
                "type": "swap",
                "spot": False,
                "swap": True,
                "contract": True,
                "linear": True,
            },
        }
        self.tickers = {}
        self.ohlcv = {}
        self.balance = {
            "USDT": {"free": 900.0, "used": 100.0, "total": 1000.0}
        }
        self.positions = []

    def load_markets(self):
        return self.markets

    def fetch_ticker(self, symbol):
        if symbol in self.tickers:
            return self.tickers[symbol]
        # پیش‌فرض حجم متناسب
        return {
            "symbol": symbol,
            "last": 50000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "high": 51000.0,
            "low": 49000.0,
            "baseVolume": 100.0,
            "quoteVolume": 5_000_000.0,
            "timestamp": int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
        }

    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        if symbol not in self.ohlcv or timeframe not in self.ohlcv.get(symbol, {}):
            raise ValueError("No OHLCV data for test")
        return self.ohlcv[symbol][timeframe]

    def fetch_balance(self):
        return self.balance

    def fetch_positions(self):
        return self.positions


@pytest.fixture
def fake_exchange(monkeypatch):
    fake = FakeExchange()
    monkeypatch.setattr(gate_exchange.ccxt, "gate", lambda options: fake)
    return fake


# ---------- تست‌ها ----------

def test_exchange_adapter_initializes(fake_exchange):
    adapter = GateExchange()
    assert adapter.exchange_id == "gateio"


def test_correct_exchange_id_is_used(fake_exchange):
    adapter = GateExchange(exchange_id="gateio")
    assert adapter.exchange_id == "gateio"


def test_default_type_is_swap_perpetual(fake_exchange):
    adapter = GateExchange()
    assert adapter.options.get("defaultType") == "swap"


def test_credentials_loaded_without_exposure(fake_exchange):
    adapter = GateExchange(options={"apiKey": "test_key", "secret": "test_secret", "defaultType": "swap"})
    assert "apiKey" not in str(adapter.exchange)
    assert "secret" not in str(adapter.exchange)


def test_public_access_works_without_credentials(fake_exchange):
    adapter = GateExchange(options={"defaultType": "swap"})
    adapter.load_markets()
    market = adapter.get_market("BTC/USDT:USDT")
    assert market["symbol"] == "BTC/USDT:USDT"


def test_private_access_without_credentials_fails(fake_exchange):
    adapter = GateExchange(options={"defaultType": "swap"})
    with pytest.raises(PermissionError):
        adapter.get_balance()


def test_markets_load_successfully(fake_exchange):
    adapter = GateExchange()
    markets = adapter.load_markets()
    assert "BTC/USDT:USDT" in markets


def test_valid_usdt_perpetual_accepted(fake_exchange):
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.validate_perpetual_symbol("BTC/USDT:USDT")
    assert result["symbol"] == "BTC/USDT:USDT"
    assert result["linear"] is True


def test_spot_market_rejected(fake_exchange):
    adapter = GateExchange()
    adapter.load_markets()
    with pytest.raises(ValueError, match="Spot market"):
        adapter.validate_perpetual_symbol("BTC/USDT")


def test_wrong_settlement_rejected(fake_exchange):
    adapter = GateExchange()
    adapter.load_markets()
    # تغییر settle برای تست
    adapter.markets["BTC/USDT:USDT"]["settle"] = "USD"
    with pytest.raises(ValueError, match="settlement"):
        adapter.validate_perpetual_symbol("BTC/USDT:USDT")


def test_non_perpetual_contract_rejected(fake_exchange):
    adapter = GateExchange()
    adapter.load_markets()
    adapter.markets["BTC/USDT:USDT"]["swap"] = False
    adapter.markets["BTC/USDT:USDT"]["contract"] = False
    with pytest.raises(ValueError, match="contract/swap"):
        adapter.validate_perpetual_symbol("BTC/USDT:USDT")


def test_unknown_symbol_rejected(fake_exchange):
    adapter = GateExchange()
    adapter.load_markets()
    with pytest.raises(ValueError, match="Symbol not found"):
        adapter.get_market("UNKNOWN/USDT:USDT")


def test_ticker_normalized(fake_exchange):
    adapter = GateExchange()
    ticker = adapter.get_ticker("BTC/USDT:USDT")
    assert ticker["symbol"] == "BTC/USDT:USDT"
    assert "last" in ticker
    assert "quote_volume" in ticker
    assert ticker["quote_volume"] == 5_000_000.0


def test_ohlcv_normalized_to_dataframe(fake_exchange):
    adapter = GateExchange()
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    timestamps = [now + timedelta(minutes=5*i) for i in range(5)]
    raw = [
        [int(ts.timestamp()*1000), 100.0, 105.0, 95.0, 102.0, 10.0]
        for ts in timestamps
    ]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    df = adapter.get_ohlcv("BTC/USDT:USDT", "5m")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.is_monotonic_increasing
    assert df.index.tz is not None


def test_required_ohlcv_columns_validated(fake_exchange):
    adapter = GateExchange()
    raw = [[int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000), 100.0, 105.0]]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    with pytest.raises(ValueError, match="Missing OHLCV column"):
        adapter.get_ohlcv("BTC/USDT:USDT", "5m")


def test_ohlcv_timestamps_chronological(fake_exchange):
    adapter = GateExchange()
    t1 = datetime(2025,1,1,tzinfo=timezone.utc)
    t2 = datetime(2025,1,1,0,10,tzinfo=timezone.utc)
    raw = [
        [int(t2.timestamp()*1000), 101, 106, 96, 103, 10],
        [int(t1.timestamp()*1000), 100, 105, 95, 102, 10],
    ]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    with pytest.raises(ValueError, match="not sorted"):
        adapter.get_ohlcv("BTC/USDT:USDT", "5m")


def test_duplicate_timestamps_rejected(fake_exchange):
    adapter = GateExchange()
    t1 = datetime(2025,1,1,tzinfo=timezone.utc)
    raw = [
        [int(t1.timestamp()*1000), 100, 105, 95, 102, 10],
        [int(t1.timestamp()*1000), 101, 106, 96, 103, 10],
    ]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    with pytest.raises(ValueError, match="duplicates"):
        adapter.get_ohlcv("BTC/USDT:USDT", "5m")


def test_unsorted_timestamps_rejected(fake_exchange):
    adapter = GateExchange()
    t1 = datetime(2025,1,1,tzinfo=timezone.utc)
    t2 = datetime(2025,1,1,0,10,tzinfo=timezone.utc)
    raw = [
        [int(t2.timestamp()*1000), 101, 106, 96, 103, 10],
        [int(t1.timestamp()*1000), 100, 105, 95, 102, 10],
    ]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    with pytest.raises(ValueError, match="not sorted"):
        adapter.get_ohlcv("BTC/USDT:USDT", "5m")


def test_malformed_ohlcv_rejected(fake_exchange):
    adapter = GateExchange()
    raw = [[int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000), "invalid", 105, 95, 102, 10]]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    with pytest.raises(ValueError, match="non-numeric"):
        adapter.get_ohlcv("BTC/USDT:USDT", "5m")


def test_5m_accepted(fake_exchange):
    adapter = GateExchange()
    assert "5m" in SUPPORTED_TIMEFRAMES


def test_1h_accepted(fake_exchange):
    adapter = GateExchange()
    assert "1h" in SUPPORTED_TIMEFRAMES


def test_4h_accepted(fake_exchange):
    adapter = GateExchange()
    assert "4h" in SUPPORTED_TIMEFRAMES


def test_unsupported_timeframe_rejected(fake_exchange):
    adapter = GateExchange()
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        adapter.get_ohlcv("BTC/USDT:USDT", "15m")


def test_incomplete_latest_candle_excluded(fake_exchange):
    adapter = GateExchange()
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t1 = now
    t2 = now + timedelta(minutes=5)
    raw = [
        [int(t1.timestamp()*1000), 100, 105, 95, 102, 10],
        [int(t2.timestamp()*1000), 103, 108, 98, 106, 10],
    ]
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    df = adapter.get_ohlcv("BTC/USDT:USDT", "5m", closed_only=True, current_time=now + timedelta(minutes=3))
    assert len(df) == 1


def test_closed_only_behavior_correct(fake_exchange):
    adapter = GateExchange()
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    raw = []
    for i in range(3):
        ts = now + timedelta(minutes=5*i)
        raw.append([int(ts.timestamp()*1000), 100+i, 105+i, 95+i, 102+i, 10])
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = raw
    df = adapter.get_ohlcv("BTC/USDT:USDT", "5m", closed_only=True, current_time=now + timedelta(minutes=7))
    # فقط کندل اول بسته شده (00:00 تا 00:05) و زمان مرجع 00:07، کندل دوم هنوز باز است
    assert len(df) == 1


def test_empty_ohlcv_handled(fake_exchange):
    adapter = GateExchange()
    fake_exchange.ohlcv.setdefault("BTC/USDT:USDT", {})["5m"] = []
    df = adapter.get_ohlcv("BTC/USDT:USDT", "5m")
    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_network_exception_handled(fake_exchange, monkeypatch):
    adapter = GateExchange()
    def raise_network(*args, **kwargs):
        raise ConnectionError("Network down")
    monkeypatch.setattr(adapter.exchange, "fetch_ticker", raise_network)
    with pytest.raises(ConnectionError, match="Network down"):
        adapter.get_ticker("BTC/USDT:USDT")


def test_authentication_exception_handled(fake_exchange, monkeypatch):
    adapter = GateExchange(options={"apiKey": "key", "secret": "secret", "defaultType": "swap"})
    def raise_auth(*args, **kwargs):
        raise PermissionError("Authentication error")
    monkeypatch.setattr(adapter.exchange, "fetch_balance", raise_auth)
    with pytest.raises(PermissionError, match="Authentication error"):
        adapter.get_balance()


def test_balance_normalized(fake_exchange):
    adapter = GateExchange(options={"apiKey": "key", "secret": "secret", "defaultType": "swap"})
    fake_exchange.balance = {
        "USDT": {"free": 900.0, "used": 100.0, "total": 1000.0}
    }
    result = adapter.get_balance()
    assert result["currency"] == "USDT"
    assert result["free"] == 900.0
    assert result["used"] == 100.0
    assert result["total"] == 1000.0


def test_positions_normalized(fake_exchange):
    adapter = GateExchange(options={"apiKey": "key", "secret": "secret", "defaultType": "swap"})
    fake_exchange.positions = [
        {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "contracts": 0.5,
            "entryPrice": 50000.0,
            "markPrice": 51000.0,
            "unrealizedPnl": 500.0,
            "leverage": 10,
        }
    ]
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT:USDT"
    assert positions[0]["side"] == "long"
    assert positions[0]["entry_price"] == 50000.0


def test_missing_position_fields_become_none(fake_exchange):
    adapter = GateExchange(options={"apiKey": "key", "secret": "secret", "defaultType": "swap"})
    fake_exchange.positions = [{"symbol": "BTC/USDT:USDT"}]
    positions = adapter.get_positions()
    assert positions[0]["side"] is None
    assert positions[0]["contracts"] is None
    assert positions[0]["entry_price"] is None
    assert positions[0]["mark_price"] is None
    assert positions[0]["unrealized_pnl"] is None
    assert positions[0]["leverage"] is None


# ---------- تست‌های حجم ----------

def _set_ticker(fake_exchange, symbol, quote_volume):
    fake_exchange.tickers[symbol] = {
        "symbol": symbol,
        "last": 100,
        "bid": 99,
        "ask": 101,
        "high": 110,
        "low": 90,
        "baseVolume": 10,
        "quoteVolume": quote_volume,
        "timestamp": 0,
    }


def test_volume_above_1m_is_eligible(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 1_500_000.0)
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is True
    assert result["volume_24h_usdt"] == 1_500_000.0


def test_volume_below_1m_is_rejected(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 999_999.0)
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is False
    assert "below minimum" in result["reason"]


def test_exact_boundary_is_eligible(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", MIN_24H_VOLUME_USDT)
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is True


def test_very_low_volume_is_rejected(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 100_000.0)
    adapter = GateExchange()
    adapter.load_markets()
    assert adapter.is_market_eligible("BTC/USDT:USDT")["eligible"] is False


def test_missing_quote_volume_is_rejected(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", None)
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is False
    assert "unavailable" in result["reason"]


def test_none_quote_volume_is_rejected(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", None)
    adapter = GateExchange()
    adapter.load_markets()
    assert adapter.is_market_eligible("BTC/USDT:USDT")["eligible"] is False


def test_malformed_quote_volume_is_rejected(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", "invalid")
    adapter = GateExchange()
    adapter.load_markets()
    assert adapter.is_market_eligible("BTC/USDT:USDT")["eligible"] is False


def test_volume_from_unrelated_timeframe_not_used(fake_exchange):
    # تست‌که فقط quote_volume استفاده می‌شود و baseVolume صرفاً نادیده گرفته می‌شود
    fake_exchange.tickers["BTC/USDT:USDT"] = {
        "quoteVolume": 5_000_000.0,
        "baseVolume": 50.0,
    }
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is True
    assert result["volume_24h_usdt"] == 5_000_000.0


def test_base_volume_alone_not_treated_as_quote(fake_exchange):
    fake_exchange.tickers["BTC/USDT:USDT"] = {
        "baseVolume": 5_000_000.0,
        "quoteVolume": None,
    }
    adapter = GateExchange()
    adapter.load_markets()
    result = adapter.is_market_eligible("BTC/USDT:USDT")
    assert result["eligible"] is False
    assert "unavailable" in result["reason"]


def test_get_eligible_markets_excludes_low_volume(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 2_000_000.0)
    _set_ticker(fake_exchange, "ETH/USDT:USDT", 999_999.0)
    _set_ticker(fake_exchange, "XRP/USDT:USDT", 1_500_000.0)
    adapter = GateExchange()
    adapter.load_markets()
    eligible = adapter.get_eligible_markets()
    symbols = {m["symbol"] for m in eligible}
    assert "BTC/USDT:USDT" in symbols
    assert "ETH/USDT:USDT" not in symbols
    assert "XRP/USDT:USDT" in symbols


def test_get_eligible_markets_excludes_spot(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 2_000_000.0)
    _set_ticker(fake_exchange, "BTC/USDT", 5_000_000.0)
    adapter = GateExchange()
    adapter.load_markets()
    eligible = adapter.get_eligible_markets()
    symbols = {m["symbol"] for m in eligible}
    assert "BTC/USDT" not in symbols
    assert "BTC/USDT:USDT" in symbols


def test_get_eligible_markets_excludes_non_perpetual(fake_exchange):
    # تغییر نوع ETH به spot? در fake بازار ETH swap است؛ فقط symbol نامعتبر می‌کنیم
    adapter = GateExchange()
    adapter.load_markets()
    adapter.markets["ETH/USDT:USDT"]["swap"] = False
    adapter.markets["ETH/USDT:USDT"]["contract"] = False
    _set_ticker(fake_exchange, "ETH/USDT:USDT", 2_000_000.0)
    eligible = adapter.get_eligible_markets()
    assert "ETH/USDT:USDT" not in [m["symbol"] for m in eligible]


def test_get_eligible_markets_returns_only_valid_usdt_markets(fake_exchange):
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 3_000_000.0)
    _set_ticker(fake_exchange, "ETH/USDT:USDT", 500_000.0)
    adapter = GateExchange()
    adapter.load_markets()
    eligible = adapter.get_eligible_markets()
    assert len(eligible) == 2  # BTC و XRP از قبل XRP volume? باید XRP هم set شود
    # ری‌ست و فقط BTC با حجم کافی
    fake_exchange.tickers = {}
    _set_ticker(fake_exchange, "BTC/USDT:USDT", 3_000_000.0)
    eligible = adapter.get_eligible_markets()
    assert all(m["symbol"] == "BTC/USDT:USDT" for m in eligible)


# ---------- تست‌های امنیتی ----------

def test_api_key_never_returned(fake_exchange):
    adapter = GateExchange(options={"apiKey": "secret_key", "secret": "secret_val", "defaultType": "swap"})
    ticker = adapter.get_ticker("BTC/USDT:USDT")
    assert "secret_key" not in str(ticker)
    assert "secret_val" not in str(ticker)


def test_secret_never_returned(fake_exchange):
    adapter = GateExchange(options={"apiKey": "key", "secret": "my_secret", "defaultType": "swap"})
    result = adapter.get_market("BTC/USDT:USDT")
    assert "my_secret" not in str(result)


def test_credentials_never_included_in_errors(fake_exchange):
    adapter = GateExchange(options={"apiKey": "key", "secret": "secret_value", "defaultType": "swap"})
    try:
        adapter.get_market("UNKNOWN")
    except ValueError as e:
        assert "secret_value" not in str(e)
        assert "key" not in str(e)


def test_no_order_endpoint_called(fake_exchange):
    adapter = GateExchange()
    # هیچ متدی از صرافی برای سفارش نباید فراخوانی شود
    assert hasattr(adapter.exchange, "create_order") is False


def test_no_write_endpoint_called(fake_exchange):
    adapter = GateExchange()
    assert hasattr(adapter, "create_order") is False
    assert hasattr(adapter, "cancel_order") is False
    assert hasattr(adapter, "edit_order") is False
    assert hasattr(adapter, "withdraw") is False
    assert hasattr(adapter, "deposit") is False


def test_no_create_order_method_exposed(fake_exchange):
    adapter = GateExchange()
    assert not hasattr(adapter, "create_order")
    assert not hasattr(adapter, "place_order")


def test_no_cancel_order_method_exposed(fake_exchange):
    adapter = GateExchange()
    assert not hasattr(adapter, "cancel_order")


def test_no_edit_order_method_exposed(fake_exchange):
    adapter = GateExchange()
    assert not hasattr(adapter, "edit_order")


def test_no_withdraw_deposit_method_exposed(fake_exchange):
    adapter = GateExchange()
    assert not hasattr(adapter, "withdraw")
    assert not hasattr(adapter, "deposit")


def test_no_live_trading_escape_hatch(fake_exchange):
    adapter = GateExchange()
    source = inspect.getsource(GateExchange)
    assert "create_order" not in source
    assert "cancel_order" not in source
    assert "close_position" not in source
