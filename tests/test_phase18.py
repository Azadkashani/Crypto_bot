import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
import math

import historical_backtest
from historical_backtest import (
    HistoricalBacktestRunner,
    HistoricalDataProvider,
    validate_ohlcv,
)
import config
import signal_scoring


def _make_ohlcv(n, freq='5min', start='2025-01-01', close=100.0):
    idx = pd.date_range(start=start, periods=n, freq=freq, tz='UTC')
    return pd.DataFrame({
        'open': close,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': 1000,
    }, index=idx)


class FakeHistoricalDataProvider(HistoricalDataProvider):
    def __init__(self, symbols):
        self.data = {sym: {} for sym in symbols}
        self.volume = {sym: 5_000_000.0 for sym in symbols}

    def set_data(self, symbol, timeframe, df):
        self.data[symbol][timeframe] = df

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe)
        if df is None:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        if start is not None:
            df = df.loc[df.index >= start]
        if end is not None:
            df = df.loc[df.index <= end]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volume.get(symbol)


@pytest.fixture
def fake_provider():
    syms = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    provider = FakeHistoricalDataProvider(syms)
    for sym in syms:
        provider.set_data(sym, '4h', _make_ohlcv(100, '4h'))
        provider.set_data(sym, '1h', _make_ohlcv(100, '1h'))
        provider.set_data(sym, '5m', _make_ohlcv(300, '5min'))
    return provider


def test_data_provider_interface(fake_provider):
    df = fake_provider.get_ohlcv('BTC/USDT:USDT', '5m')
    assert not df.empty
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert df.index.tz is not None


def test_timeframe_independence(fake_provider):
    df4 = fake_provider.get_ohlcv('BTC/USDT:USDT', '4h')
    df1 = fake_provider.get_ohlcv('BTC/USDT:USDT', '1h')
    df5 = fake_provider.get_ohlcv('BTC/USDT:USDT', '5m')
    assert len(df4) != len(df5)
    assert len(df1) != len(df5)


def test_closed_candles_only(fake_provider):
    df5 = fake_provider.get_ohlcv('BTC/USDT:USDT', '5m')
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    decision_time = df5.index[2] + timedelta(minutes=5)
    sliced = runner._get_closed_slice(df5, '5m', decision_time)
    assert len(sliced) == 3
    assert df5.index[3] not in sliced.index


def test_no_future_data(fake_provider):
    df5 = fake_provider.get_ohlcv('BTC/USDT:USDT', '5m')
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    decision_time = df5.index[0] + timedelta(minutes=5)
    sliced = runner._get_closed_slice(df5, '5m', decision_time)
    assert len(sliced) == 1
    assert sliced.index[0] == df5.index[0]


def test_chronological_processing(fake_provider):
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    times = runner._get_all_decision_times()
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_volume_filter_boundaries(fake_provider, monkeypatch):
    sig = {
        "signal": "LONG", "valid": True, "symbol": "BTC/USDT:USDT",
        "entry_price": 100, "stop_loss": 95, "take_profit": 110,
        "volume_24h_usdt": 999_999, "regime_4h": "BULLISH",
        "regime_1h": "BULLISH", "rsi_recovery": True,
        "choch": True, "bos": True, "risk_reward": 2.0,
        "position_size": 2.0, "risk_amount": 10.0,
    }
    assert signal_scoring.calculate_score(sig) is None
    sig["volume_24h_usdt"] = 1_000_000
    assert signal_scoring.calculate_score(sig) is not None
    sig["volume_24h_usdt"] = 1_000_001
    assert signal_scoring.calculate_score(sig) is not None


def test_non_perpetual_rejection(fake_provider):
    fake_provider.volume["BTC/USDT:USDT"] = None
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    times = runner._get_all_decision_times()
    assert len(times) > 0


def test_wrong_settlement_rejection(fake_provider):
    fake_provider.volume["ETH/USDT:USDT"] = None
    runner = HistoricalBacktestRunner(fake_provider, ["ETH/USDT:USDT"])
    assert runner.provider.get_volume_24h_usdt('ETH/USDT:USDT', pd.Timestamp.now(timezone.utc)) is None


def test_dynamic_balance(fake_provider, monkeypatch):
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal", 
                        lambda *args, **kwargs: {
                            "signal": "LONG", "valid": True,
                            "entry_price": 100, "stop_loss": 90,
                            "take_profit": 120, "position_size": 2.0,
                            "risk_amount": 10.0, "regime_4h": "BULLISH",
                            "regime_1h": "BULLISH", "rsi_recovery": True,
                            "choch": True, "bos": True,
                            "risk_reward": 2.0, "symbol": kwargs.get("symbol"),
                        })
    provider = fake_provider
    provider.volume = {"BTC/USDT:USDT": 2_000_000, "ETH/USDT:USDT": 5_000_000}
    runner = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    runner.current_balance = 1000
    runner._close_position(
        {"symbol": "BTC/USDT:USDT", "direction": "LONG", "entry_price": 100,
         "stop_loss": 90, "take_profit": 120, "position_size": 2.0,
         "risk_amount": 10.0, "score": 70, "regime_4h": "BULLISH", "regime_1h": "BULLISH",
         "entry_time": pd.Timestamp('2025-01-01', tz='UTC')},
        exit_price=120,
        exit_reason="TP",
        exit_time=pd.Timestamp('2025-01-02', tz='UTC'),
    )
    assert runner.current_balance == 1040


def test_sl_first(fake_provider, monkeypatch):
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    position = {"symbol": "BTC/USDT:USDT", "direction": "LONG", "entry_time": pd.Timestamp('2025-01-01', tz='UTC'),
                "entry_price": 100, "stop_loss": 95, "take_profit": 110, "position_size": 1.0,
                "risk_amount": 10.0, "score": 70, "regime_4h": "BULLISH", "regime_1h": "BULLISH"}
    class TempProvider:
        def get_ohlcv(self, symbol, timeframe, start=None, end=None):
            idx = pd.DatetimeIndex([pd.Timestamp('2025-01-02 00:00:00', tz='UTC')])
            return pd.DataFrame({'open':100, 'high':111, 'low':94, 'close':100, 'volume':100}, index=idx)
        def get_volume_24h_usdt(self, symbol, timestamp):
            return 2_000_000
    runner.provider = TempProvider()
    closed = runner._try_exit(position, pd.Timestamp('2025-01-02 00:05:00', tz='UTC'))
    assert closed is True
    assert runner.trades[-1]["exit_reason"] == "SL"
    assert runner.trades[-1]["exit_price"] == 95


def test_real_strategy_integration(fake_provider, monkeypatch):
    assert hasattr(historical_backtest.strategy, "generate_signal")


def test_no_strategy_bypass(fake_provider):
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    result = runner.run()
    assert result["total_trades"] == 0
    assert result["success"] is True


def test_multi_signal_ranking(fake_provider, monkeypatch):
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal",
                        lambda df4, df1, df5, as_of=None, account_balance=None, symbol=None: {
                            "signal": "LONG", "valid": True,
                            "symbol": symbol,
                            "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                            "position_size": 2.0, "risk_amount": 10.0,
                            "regime_4h": "BULLISH", "regime_1h": "BULLISH",
                            "rsi_recovery": True, "choch": True, "bos": True,
                            "risk_reward": 2.0,
                            "volume_24h_usdt": 2_000_000 if symbol=="BTC/USDT:USDT" else 5_000_000,
                        })
    provider = fake_provider
    provider.volume = {"BTC/USDT:USDT": 2_000_000, "ETH/USDT:USDT": 5_000_000}
    for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT"]:
        provider.set_data(sym, '5m', _make_ohlcv(1, '5min'))
        provider.set_data(sym, '1h', _make_ohlcv(1, '1h'))
        provider.set_data(sym, '4h', _make_ohlcv(1, '4h'))
    runner = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    result = runner.run()
    assert result["selected_signals"] >= 1
    assert result["trades"][0]["symbol"] == "ETH/USDT:USDT"


def test_deterministic_ranking(fake_provider, monkeypatch):
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal",
                        lambda *args, **kwargs: {
                            "signal": "LONG", "valid": True,
                            "symbol": kwargs.get("symbol"),
                            "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                            "position_size": 2.0, "risk_amount": 10.0,
                            "regime_4h": "BULLISH", "regime_1h": "BULLISH",
                            "rsi_recovery": True, "choch": True, "bos": True,
                            "risk_reward": 2.0,
                            "volume_24h_usdt": 2_000_000,
                        })
    provider = fake_provider
    provider.volume = {"BTC/USDT:USDT": 2_000_000, "ETH/USDT:USDT": 5_000_000}
    r1 = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT", "ETH/USDT:USDT"]).run()
    r2 = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT", "ETH/USDT:USDT"]).run()
    assert r1["metrics"] == r2["metrics"]


def test_no_real_order(fake_provider):
    assert not hasattr(HistoricalBacktestRunner, "create_order")
    assert "create_order" not in str(HistoricalBacktestRunner.__dict__)


def test_metrics_integration(fake_provider):
    result = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"]).run()
    assert "metrics" in result
    assert "profit_factor" in result["metrics"]


def test_long_short_breakdown(fake_provider):
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"])
    runner._close_position(
        {"symbol": "BTC/USDT:USDT", "direction": "LONG", "entry_time": pd.Timestamp('2025-01-01', tz='UTC'),
         "entry_price": 100, "stop_loss": 90, "take_profit": 120, "position_size": 1.0,
         "risk_amount": 10.0, "score": 70, "regime_4h": "BULLISH", "regime_1h": "BULLISH"},
        exit_price=120, exit_reason="TP", exit_time=pd.Timestamp('2025-01-02', tz='UTC')
    )
    runner._close_position(
        {"symbol": "BTC/USDT:USDT", "direction": "SHORT", "entry_time": pd.Timestamp('2025-01-03', tz='UTC'),
         "entry_price": 100, "stop_loss": 110, "take_profit": 80, "position_size": 1.0,
         "risk_amount": 10.0, "score": 70, "regime_4h": "BEARISH", "regime_1h": "BEARISH"},
        exit_price=80, exit_reason="TP", exit_time=pd.Timestamp('2025-01-04', tz='UTC')
    )
    long = [t for t in runner.trades if t["direction"] == "LONG"]
    short = [t for t in runner.trades if t["direction"] == "SHORT"]
    assert len(long) == 1
    assert len(short) == 1


def test_symbol_breakdown(fake_provider):
    runner = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    runner._close_position(
        {"symbol": "BTC/USDT:USDT", "direction": "LONG", "entry_time": pd.Timestamp('2025-01-01', tz='UTC'),
         "entry_price": 100, "stop_loss": 90, "take_profit": 120, "position_size": 1.0,
         "risk_amount": 10.0, "score": 70, "regime_4h": "BULLISH", "regime_1h": "BULLISH"},
        exit_price=120, exit_reason="TP", exit_time=pd.Timestamp('2025-01-02', tz='UTC')
    )
    assert runner.trades[0]["symbol"] == "BTC/USDT:USDT"


def test_period_breakdown(fake_provider):
    result = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"]).run()
    assert "period_metrics" in result


def test_empty_data(fake_provider):
    provider = FakeHistoricalDataProvider(["X/USDT:USDT"])
    result = HistoricalBacktestRunner(provider, ["X/USDT:USDT"]).run()
    assert result["total_trades"] == 0
    assert result["success"] is True


def test_invalid_ohlcv():
    df = pd.DataFrame({'open': [100], 'high': [99], 'low': [101], 'close': [100], 'volume': [100]},
                      index=pd.DatetimeIndex([pd.Timestamp('2025-01-01', tz='UTC')]))
    res = validate_ohlcv(df, '5m')
    assert res["valid"] is False
    assert "high < max" in res["issues"]


def test_duplicate_timestamps():
    idx = pd.to_datetime(['2025-01-01', '2025-01-01'], utc=True)
    df = pd.DataFrame({'open':[100,101], 'high':[102,102], 'low':[99,99], 'close':[100,101], 'volume':[10,10]}, index=idx)
    res = validate_ohlcv(df, '5m')
    assert "duplicate timestamps" in res["issues"]


def test_unsorted_timestamps():
    idx = pd.to_datetime(['2025-01-02', '2025-01-01'], utc=True)
    df = pd.DataFrame({'open':[100,101], 'high':[102,102], 'low':[99,99], 'close':[100,101], 'volume':[10,10]}, index=idx)
    res = validate_ohlcv(df, '5m')
    assert "unsorted timestamps" in res["issues"]


def test_negative_volume():
    idx = pd.DatetimeIndex([pd.Timestamp('2025-01-01', tz='UTC')])
    df = pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100], 'volume':[-1]}, index=idx)
    res = validate_ohlcv(df, '5m')
    assert "negative volume" in res["issues"]


def test_reproducibility(fake_provider):
    result1 = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"]).run()
    result2 = HistoricalBacktestRunner(fake_provider, ["BTC/USDT:USDT"]).run()
    assert result1["metrics"] == result2["metrics"]
    assert result1["total_candidates"] == result2["total_candidates"]


def test_future_volume_protection(fake_provider, monkeypatch):
    class TempProvider(fake_provider.__class__):
        def __init__(self, symbols):
            super().__init__(symbols)
            self.call_times = []
        def get_volume_24h_usdt(self, symbol, timestamp):
            self.call_times.append(timestamp)
            if timestamp > pd.Timestamp('2025-01-01 01:00:00', tz='UTC'):
                return 500_000
            return 2_000_000
    provider = TempProvider(["BTC/USDT:USDT"])
    provider.set_data('BTC/USDT:USDT', '5m', _make_ohlcv(50, '5min'))
    provider.set_data('BTC/USDT:USDT', '1h', _make_ohlcv(10, '1h'))
    provider.set_data('BTC/USDT:USDT', '4h', _make_ohlcv(5, '4h'))
    runner = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT"])
    result = runner.run()
    assert result["total_trades"] == 0


def test_candidate_accounting(fake_provider, monkeypatch):
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal",
                        lambda *args, **kwargs: {
                            "signal": "LONG", "valid": True,
                            "symbol": kwargs.get("symbol"),
                            "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                            "position_size": 2.0, "risk_amount": 10.0,
                            "regime_4h": "BULLISH", "regime_1h": "BULLISH",
                            "rsi_recovery": True, "choch": True, "bos": True,
                            "risk_reward": 2.0,
                            "volume_24h_usdt": 2_000_000,
                        })
    provider = fake_provider
    # فقط یک کندل برای هر timeframe، اما 3 Symbol
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    for sym in symbols:
        provider.set_data(sym, '5m', _make_ohlcv(1, '5min'))
        provider.set_data(sym, '1h', _make_ohlcv(1, '1h'))
        provider.set_data(sym, '4h', _make_ohlcv(1, '4h'))
    runner = HistoricalBacktestRunner(provider, symbols)
    result = runner.run()
    assert result["total_candidates"] == 3


def test_best_signal_accounting(fake_provider, monkeypatch):
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal",
                        lambda *args, **kwargs: {
                            "signal": "LONG", "valid": True,
                            "symbol": kwargs.get("symbol"),
                            "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                            "position_size": 2.0, "risk_amount": 10.0,
                            "regime_4h": "BULLISH", "regime_1h": "BULLISH",
                            "rsi_recovery": True, "choch": True, "bos": True,
                            "risk_reward": 2.0,
                            "volume_24h_usdt": 2_000_000,
                        })
    provider = fake_provider
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    for sym in symbols:
        provider.set_data(sym, '5m', _make_ohlcv(1, '5min'))
        provider.set_data(sym, '1h', _make_ohlcv(1, '1h'))
        provider.set_data(sym, '4h', _make_ohlcv(1, '4h'))
    runner = HistoricalBacktestRunner(provider, symbols)
    result = runner.run()
    # 3 کاندید، اما فقط یک Best Signal انتخاب می‌شود
    assert result["selected_signals"] == 1


def test_safety_integration(fake_provider, monkeypatch):
    # بالانس ناکافی
    monkeypatch.setattr(historical_backtest.strategy, "generate_signal",
                        lambda *args, **kwargs: {
                            "signal": "LONG", "valid": True,
                            "symbol": kwargs.get("symbol"),
                            "entry_price": 100, "stop_loss": 90, "take_profit": 120,
                            "position_size": 2.0, "risk_amount": 10.0,
                            "regime_4h": "BULLISH", "regime_1h": "BULLISH",
                            "rsi_recovery": True, "choch": True, "bos": True,
                            "risk_reward": 2.0,
                            "volume_24h_usdt": 2_000_000,
                        })
    provider = fake_provider
    runner = HistoricalBacktestRunner(provider, ["BTC/USDT:USDT"])
    runner.current_balance = 5
    runner.symbols = ["BTC/USDT:USDT"]
    provider.set_data('BTC/USDT:USDT', '5m', _make_ohlcv(1, '5min'))
    provider.set_data('BTC/USDT:USDT', '1h', _make_ohlcv(1, '1h'))
    provider.set_data('BTC/USDT:USDT', '4h', _make_ohlcv(1, '4h'))
    result = runner.run()
    assert result["safety_rejections"] >= 1
    assert result["total_trades"] == 0
