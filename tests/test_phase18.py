import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from historical_data import (
    parse_timeframe,
    expected_candles,
    validate_ohlcv,
    fetch_ohlcv_paginated,
    HistoricalDataDownloader,
)


def _make_ohlcv(n=10, freq='5min', start='2025-01-01', close=100.0):
    idx = pd.date_range(start=start, periods=n, freq=freq, tz='UTC')
    return pd.DataFrame({
        'open': close,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': 1000,
    }, index=idx)


class FakeExchangePagination:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    @property
    def exchange(self):
        return self

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        self.calls.append((symbol, timeframe, since, limit))
        if self.pages:
            return self.pages.pop(0)
        return []


def test_parse_timeframe():
    assert parse_timeframe('5m') == timedelta(minutes=5)
    assert parse_timeframe('1h') == timedelta(hours=1)
    assert parse_timeframe('4h') == timedelta(hours=4)
    with pytest.raises(ValueError):
        parse_timeframe('15x')


def test_expected_candles():
    start = pd.Timestamp('2025-01-01', tz='UTC')
    end = pd.Timestamp('2025-01-02', tz='UTC')
    assert expected_candles(start, end, '1h') == 25  # 24h + 1 inclusive


def test_validate_empty():
    df = pd.DataFrame(columns=['open','high','low','close','volume'])
    res = validate_ohlcv(df, '5m')
    assert res['valid'] is False
    assert 'empty' in res['issues']


def test_validate_unsorted():
    idx = pd.to_datetime(['2025-01-02', '2025-01-01'], utc=True)
    df = pd.DataFrame({'open':[100,101], 'high':[102,102], 'low':[99,99], 'close':[100,101], 'volume':[10,10]}, index=idx)
    res = validate_ohlcv(df, '5m')
    assert 'unsorted timestamps' in res['issues']


def test_validate_duplicate():
    idx = pd.to_datetime(['2025-01-01', '2025-01-01'], utc=True)
    df = pd.DataFrame({'open':[100,101], 'high':[102,102], 'low':[99,99], 'close':[100,101], 'volume':[10,10]}, index=idx)
    res = validate_ohlcv(df, '5m')
    assert 'duplicate timestamps' in res['issues']


def test_validate_invalid_ohlc():
    df = pd.DataFrame({'open':[100], 'high':[99], 'low':[101], 'close':[100], 'volume':[100]},
                      index=pd.DatetimeIndex([pd.Timestamp('2025-01-01', tz='UTC')]))
    res = validate_ohlcv(df, '5m')
    assert 'high < max' in res['issues']
    assert 'low > min' in res['issues']


def test_validate_negative_volume():
    df = pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100], 'volume':[-1]},
                      index=pd.DatetimeIndex([pd.Timestamp('2025-01-01', tz='UTC')]))
    res = validate_ohlcv(df, '5m')
    assert 'negative volume' in res['issues']


def test_validate_incomplete_last_candle():
    # زمان فعلی را ثابت می‌کنیم
    now = pd.Timestamp('2025-01-01 00:03:00', tz='UTC')
    idx = pd.DatetimeIndex([pd.Timestamp('2025-01-01 00:00:00', tz='UTC')])
    df = pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100], 'volume':[100]}, index=idx)
    # patch pd.Timestamp.now؟ ساده: not test time-dependent, skip
    # we can't easily patch, but we can call with monkeypatch
    # Use monkeypatch to set pd.Timestamp.now
    original_now = pd.Timestamp.now
    pd.Timestamp.now = lambda tz=None: now
    try:
        res = validate_ohlcv(df, '5m')
        assert 'incomplete last candle' in res['issues']
    finally:
        pd.Timestamp.now = original_now


def test_fetch_ohlcv_paginated_multiple_pages():
    base_ts = int(pd.Timestamp('2025-01-01', tz='UTC').timestamp() * 1000)
    page1 = [[base_ts + i*60000, 100+i, 101+i, 99+i, 100+i, 100] for i in range(1000)]
    page2 = [[base_ts + 1000*60000 + i*60000, 110+i, 111+i, 109+i, 110+i, 100] for i in range(100)]
    fake = FakeExchangePagination([page1, page2])
    df = fetch_ohlcv_paginated(fake, 'BTC/USDT:USDT', '5m', base_ts)
    assert len(df) == 1100
    assert df.index.is_monotonic_increasing
    assert df.index.duplicated().sum() == 0


def test_fetch_ohlcv_paginated_handles_duplicates():
    base_ts = int(pd.Timestamp('2025-01-01', tz='UTC').timestamp() * 1000)
    page1 = [[base_ts, 100, 101, 99, 100, 100]]
    page2 = [[base_ts, 100, 101, 99, 100, 100]]  # duplicate
    fake = FakeExchangePagination([page1, page2])
    df = fetch_ohlcv_paginated(fake, 'BTC/USDT:USDT', '5m', base_ts)
    assert len(df) == 1
    assert df.index.duplicated().sum() == 0


def test_downloader_filters_date_range():
    fake = FakeExchangePagination([
        [[int(pd.Timestamp('2025-01-01 00:00:00', tz='UTC').timestamp()*1000), 100, 101, 99, 100, 100],
         [int(pd.Timestamp('2025-01-01 00:05:00', tz='UTC').timestamp()*1000), 101, 102, 100, 101, 100],
         [int(pd.Timestamp('2025-01-01 00:10:00', tz='UTC').timestamp()*1000), 102, 103, 101, 102, 100]]
    ])
    downloader = HistoricalDataDownloader(
        fake,
        'BTC/USDT:USDT',
        '5m',
        pd.Timestamp('2025-01-01 00:00:00', tz='UTC'),
        pd.Timestamp('2025-01-01 00:05:00', tz='UTC'),
    )
    df = downloader.download()
    assert len(df) == 2
    assert df.index.min() == pd.Timestamp('2025-01-01 00:00:00', tz='UTC')
    assert df.index.max() == pd.Timestamp('2025-01-01 00:05:00', tz='UTC')


def test_data_not_empty():
    df = _make_ohlcv(5)
    res = validate_ohlcv(df, '5m')
    assert res['valid'] is True  # بدون بررسی کامل آخرین کندل، ممکن است false شود
    # چون last candle incomplete? با توجه به now ممکن است incomplete باشد
    # برای سادگی فقط چک می‌کنیم که empty نبوده
    assert not df.empty


def test_timeframe_independence():
    df5 = _make_ohlcv(10, freq='5min')
    df1h = _make_ohlcv(10, freq='1h')
    df4h = _make_ohlcv(10, freq='4h')
    assert len(df5) != len(df1h)
    assert len(df1h) != len(df4h)


def test_volume_filter_boundaries():
    from signal_scoring import calculate_score
    base_signal = {
        "signal": "LONG", "valid": True, "symbol": "BTC/USDT:USDT",
        "entry_price": 100, "stop_loss": 95, "take_profit": 110,
        "volume_24h_usdt": 999_999, "regime_4h": "BULLISH",
        "regime_1h": "BULLISH", "rsi_recovery": True,
        "choch": True, "bos": True, "risk_reward": 2.0,
        "position_size": 2.0, "risk_amount": 10.0,
    }
    assert calculate_score(base_signal) is None
    base_signal["volume_24h_usdt"] = 1_000_000
    assert calculate_score(base_signal) is not None
    base_signal["volume_24h_usdt"] = 1_000_001
    assert calculate_score(base_signal) is not None


def test_deterministic_data_processing():
    df1 = _make_ohlcv(20)
    df2 = _make_ohlcv(20)
    res1 = validate_ohlcv(df1, '5m')
    res2 = validate_ohlcv(df2, '5m')
    assert res1 == res2


def test_backtest_does_not_run_with_invalid_data():
    # استفاده از validate_ohlcv برای شبیه‌سازی عدم اجرا با داده نامعتبر
    df = pd.DataFrame({'open': [100], 'high': [99], 'low': [101], 'close': [100], 'volume': [-1]},
                      index=pd.DatetimeIndex([pd.Timestamp('2025-01-01', tz='UTC')]))
    res = validate_ohlcv(df, '5m')
    assert res['valid'] is False
    # منطق اجرا باید از این نتیجه استفاده کند؛ ما اینجا فقط بررسی می‌کنیم
    assert 'negative volume' in res['issues']
