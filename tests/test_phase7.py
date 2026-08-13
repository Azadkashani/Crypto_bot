import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import strategy
import config
import indicators
import regime
import choch
import bos


def _make_index(n, freq='5min', start='2025-01-01'):
    return pd.date_range(start=start, periods=n, freq=freq, tz='UTC')


def _make_regime_df(direction, n=200, freq='4h', start='2024-01-01'):
    idx = _make_index(n, freq=freq, start=start)
    if direction == 'bullish':
        close = 100 + np.arange(n) * 1.0
    else:
        close = 100 - np.arange(n) * 1.0
    return pd.DataFrame({
        'open': close - 0.1,
        'high': close + 0.5,
        'low': close - 0.5,
        'close': close,
        'volume': 100
    }, index=idx)


def _make_5m_bullish_setup():
    n = 45
    idx = _make_index(n, '5min')
    closes = [
        100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74,
        72, 70, 72, 75, 80, 82, 83, 84, 90, 92, 94, 96, 98, 100,
        98, 96, 94, 92, 100, 101, 102, 103, 102, 101, 100, 99, 98,
        97, 96, 95, 116
    ]
    high = closes.copy()
    low = closes.copy()

    # نوسان بالای اول (index 8) - سطح 95
    high[8] = 95
    high[9] = 90
    high[10] = 89
    high[11] = 88

    # نوسان بالای دوم (Lower High) - index 18 - سطح 85
    high[18] = 85
    high[19] = 84
    high[20] = 83
    high[21] = 82

    # CHOCH در index 22 - بسته بالای 85
    closes[22] = 90
    high[22] = 91
    low[22] = 86

    # نوسان بالای جدید برای BOS - index 28 - سطح 104
    high[28] = 104
    high[29] = 100
    high[30] = 98
    high[31] = 96

    # BOS در index 44 - بسته بالای 104
    closes[44] = 116
    high[44] = 117
    low[44] = 112

    return pd.DataFrame({
        'open': [c - 0.5 for c in closes],
        'high': high,
        'low': [c - 1.0 for c in closes],
        'close': closes,
        'volume': 100
    }, index=idx)


def _make_5m_bearish_setup():
    n = 45
    idx = _make_index(n, '5min')
    closes = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126,
        128, 130, 128, 125, 120, 118, 117, 116, 110, 108, 106, 104, 102, 100,
        102, 104, 106, 108, 100, 99, 98, 97, 98, 99, 100, 101, 102,
        103, 104, 105, 84
    ]
    high = closes.copy()
    low = closes.copy()

    # کف اول (index 8) - سطح 95
    low[8] = 95
    low[9] = 98
    low[10] = 99
    low[11] = 100

    # کف دوم (Higher Low) - index 18 - سطح 105
    low[18] = 105
    low[19] = 106
    low[20] = 107
    low[21] = 108

    # CHOCH در index 22 - بسته زیر 105
    closes[22] = 110
    low[22] = 104
    high[22] = 111

    # نوسان پایین جدید برای BOS - index 28 - سطح 96
    low[28] = 96
    low[29] = 100
    low[30] = 102
    low[31] = 104

    # BOS در index 44 - بسته زیر 96
    closes[44] = 84
    low[44] = 83
    high[44] = 85

    return pd.DataFrame({
        'open': [c + 0.5 for c in closes],
        'high': high,
        'low': low,
        'close': closes,
        'volume': 100
    }, index=idx)


# ------------------------------------------------------------
# تست‌ها
# ------------------------------------------------------------

def test_long_requires_4h_and_1h_bullish():
    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"
    assert res["valid"] is False


def test_short_requires_4h_and_1h_bearish():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"


def test_no_signal_when_timeframes_not_aligned():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bullish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"


def test_long_rsi_pullback_and_recovery():
    df_5m = _make_5m_bullish_setup()
    rsi_df = indicators.add_rsi(df_5m, period=config.RSI_PERIOD)
    rsi_series = rsi_df[f'rsi_{config.RSI_PERIOD}'].dropna()
    assert rsi_series.min() <= config.RSI_OVERSOLD
    assert rsi_series.iloc[-1] > rsi_series.iloc[-2]


def test_short_rsi_pullback_and_recovery():
    df_5m = _make_5m_bearish_setup()
    rsi_df = indicators.add_rsi(df_5m, period=config.RSI_PERIOD)
    rsi_series = rsi_df[f'rsi_{config.RSI_PERIOD}'].dropna()
    assert rsi_series.max() >= config.RSI_OVERBOUGHT
    assert rsi_series.iloc[-1] < rsi_series.iloc[-2]


def test_long_requires_choch_before_bos():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup().iloc[:22]  # قبل از CHOCH
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"
    assert "CHOCH not detected" in res["reason"]


def test_short_requires_choch_before_bos():
    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup().iloc[:22]
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"


def test_long_signal_after_rsi_choch_bos():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "LONG"
    assert res["valid"] is True
    assert res["choch"] is True
    assert res["bos"] is True


def test_short_signal_after_rsi_choch_bos():
    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "SHORT"
    assert res["valid"] is True


def test_incomplete_5m_candle_not_used():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    last_start = df_5m.index[-1]
    as_of = last_start + timedelta(minutes=2)
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    assert res["signal"] == "NONE"
    assert res["bos"] is False


def test_incomplete_1h_candle_not_used():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish', freq='1h')
    df_5m = _make_5m_bullish_setup()
    last_1h_start = df_1h.index[-1]
    as_of = last_1h_start + timedelta(minutes=30)
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    assert res["signal"] == "LONG"


def test_incomplete_4h_candle_not_used():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    last_4h_start = df_4h.index[-1]
    as_of = last_4h_start + timedelta(hours=2)
    res = strategy.generate_signal(df_4h, df_1h, df_5m, as_of=as_of)
    assert res["signal"] == "LONG"


def test_no_future_data_used():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    partial = df_5m.iloc[:45]
    res = strategy.generate_signal(df_4h, df_1h, partial)
    assert res["signal"] == "LONG"


def test_wick_only_bos_not_signal():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    df_5m.loc[df_5m.index[44], 'high'] = 120
    df_5m.loc[df_5m.index[44], 'close'] = 103
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res["signal"] == "NONE"
    assert res["bos"] is False


def test_timeframe_dataframes_are_independent():
    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m_long = _make_5m_bullish_setup()
    df_5m_short = _make_5m_bearish_setup()
    res_long = strategy.generate_signal(df_4h, df_1h, df_5m_long)
    res_short = strategy.generate_signal(df_4h, df_1h, df_5m_short)
    assert res_long["signal"] != res_short["signal"]