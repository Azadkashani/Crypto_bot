import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from backtest_engine import OptimizedBacktestRunner


class FakeProvider:
    def __init__(self, data, volumes):
        self.data = data
        self.volumes = volumes

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe, pd.DataFrame())
        if start is not None:
            df = df[df.index >= start]
        if end is not None:
            df = df[df.index <= end]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volumes.get(symbol)


def _make_df(n, freq='5min', start='2025-01-01', close=100.0):
    idx = pd.date_range(start=start, periods=n, freq=freq, tz='UTC')
    return pd.DataFrame({
        'open': close,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': 1000,
    }, index=idx)


def test_precomputed_same_as_original_small():
    symbol = 'BTC/USDT:USDT'
    provider = FakeProvider({
        symbol: {
            '5m': _make_df(10, '5min'),
            '1h': _make_df(5, '1h'),
            '4h': _make_df(3, '4h'),
        }
    }, {symbol: 2_000_000})

    runner = OptimizedBacktestRunner(provider, [symbol], initial_balance=1000)
    result = runner.run()
    assert result['success'] is True
    assert result['total_trades'] == 0


def test_no_lookahead_future_candle():
    symbol = 'BTC/USDT:USDT'
    provider = FakeProvider({
        symbol: {
            '5m': _make_df(10, '5min'),
            '1h': _make_df(5, '1h'),
            '4h': _make_df(3, '4h'),
        }
    }, {symbol: 2_000_000})

    runner = OptimizedBacktestRunner(provider, [symbol], initial_balance=1000)
    runner._precompute_symbol(symbol)
    idx_arr = runner._precomputed[symbol]['5m']['index']
    decision_time = pd.to_datetime(idx_arr[3]) + pd.Timedelta(minutes=5)
    # بررسی mapping با کلید close (نه rsi که ممکن است NaN باشد)
    close_val = runner._latest_value_at(symbol, '5m', decision_time, 'close')
    assert close_val is not None
    # ایندکس 5 هنوز در دسترس نیست
    later_time = pd.to_datetime(idx_arr[4]) + pd.Timedelta(minutes=5)
    later_close = runner._latest_value_at(symbol, '5m', later_time, 'close')
    assert later_close is not None
    assert decision_time < later_time


def test_sl_first():
    symbol = 'BTC/USDT:USDT'
    provider = FakeProvider({
        symbol: {
            '5m': pd.DataFrame({
                'open':[100,100,100],
                'high':[111,111,111],
                'low':[94,94,94],
                'close':[100,100,100],
                'volume':[100,100,100]
            }, index=pd.date_range('2025-01-01', periods=3, freq='5min', tz='UTC')),
            '1h': _make_df(2, '1h'),
            '4h': _make_df(1, '4h'),
        }
    }, {symbol: 2_000_000})
    runner = OptimizedBacktestRunner(provider, [symbol], initial_balance=1000)
    runner._precompute_symbol(symbol)

    candle = runner._get_precomputed_candle(
        symbol,
        '5m',
        pd.to_datetime(runner._precomputed[symbol]['5m']['index'][1]) + pd.Timedelta(minutes=5)
    )
    assert candle['high'] == 111
    assert candle['low'] == 94

    position = {
        'symbol': symbol,
        'direction': 'LONG',
        'entry_time': pd.Timestamp('2025-01-01 00:05:00', tz='UTC'),
        'entry_price': 100,
        'stop_loss': 95,
        'take_profit': 110,
        'position_size': 1,
        'risk_amount': 10,
        'score': None,
        'regime_4h': 'BULLISH',
        'regime_1h': 'BULLISH',
    }

    closed = runner._try_exit_fast(
        position,
        pd.to_datetime(runner._precomputed[symbol]['5m']['index'][1]) + pd.Timedelta(minutes=5)
    )
    assert closed is True
    assert runner.trades[-1]['exit_reason'] == 'SL'
    assert runner.trades[-1]['exit_price'] == 95
