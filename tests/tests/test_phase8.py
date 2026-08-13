# tests/test_phase8.py
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import config
from risk_gate import evaluate_risk
import strategy


def _make_risk_df(direction='LONG'):
    """DataFrame ساده با swing های مشخص برای تست Risk Gate."""
    idx = pd.date_range(start='2025-01-01', periods=10, freq='5min', tz='UTC')
    df = pd.DataFrame({
        'open':  [100]*10,
        'high':  [101]*10,
        'low':   [99]*10,
        'close': [100]*10,
        'swing_high': [False]*10,
        'swing_low':  [False]*10,
    }, index=idx)

    if direction == 'LONG':
        # swing_low در ایندکس 2 (قیمت پایین)
        df.loc[idx[2], 'low'] = 98
        df.loc[idx[2], 'swing_low'] = True
        # BOS در ایندکس 8، کلوز بالای swing_high (اختیاری)
        df.loc[idx[8], 'close'] = 105
    else:  # SHORT
        # swing_high در ایندکس 2
        df.loc[idx[2], 'high'] = 103
        df.loc[idx[2], 'swing_high'] = True
        # BOS در ایندکس 8، کلوز زیر swing_low (اختیاری)
        df.loc[idx[8], 'close'] = 97
    return df


def test_valid_long_risk():
    df = _make_risk_df('LONG')
    bos_idx = df.index[8]
    res = evaluate_risk(df, bos_idx, 'LONG')
    assert res['valid'] is True
    assert res['entry_price'] == 105
    assert res['stop_loss'] == 98
    expected_risk = 105 - 98
    assert res['take_profit'] == 105 + expected_risk * config.RISK_REWARD
    assert res['risk_reward'] == config.RISK_REWARD


def test_valid_short_risk():
    df = _make_risk_df('SHORT')
    bos_idx = df.index[8]
    res = evaluate_risk(df, bos_idx, 'SHORT')
    assert res['valid'] is True
    assert res['entry_price'] == 97
    assert res['stop_loss'] == 103
    expected_risk = 103 - 97
    assert res['take_profit'] == 97 - expected_risk * config.RISK_REWARD


def test_invalid_long_stop_loss():
    df = _make_risk_df('LONG')
    # تغییر swing_low به بالاتر از entry => ریسک منفی
    df.loc[df.index[2], 'low'] = 110
    res = evaluate_risk(df, df.index[8], 'LONG')
    assert res['valid'] is False
    assert 'risk <= 0' in res['reason']


def test_invalid_short_stop_loss():
    df = _make_risk_df('SHORT')
    # تغییر swing_high به پایین‌تر از entry => ریسک منفی
    df.loc[df.index[2], 'high'] = 95
    res = evaluate_risk(df, df.index[8], 'SHORT')
    assert res['valid'] is False
    assert 'risk <= 0' in res['reason']


def test_zero_or_negative_risk():
    df = _make_risk_df('LONG')
    # stop برابر entry
    df.loc[df.index[2], 'low'] = 105
    res = evaluate_risk(df, df.index[8], 'LONG')
    assert res['valid'] is False


def test_missing_swing():
    df = _make_risk_df('LONG')
    df['swing_low'] = False
    df['swing_high'] = False
    res = evaluate_risk(df, df.index[8], 'LONG')
    assert res['valid'] is False
    assert 'No confirmed swing low' in res['reason']


def test_no_future_swing_used():
    df = _make_risk_df('LONG')
    # swing_low بعد از BOS (ایندکس 9)
    df.loc[df.index[9], 'swing_low'] = True
    df.loc[df.index[9], 'low'] = 99
    res = evaluate_risk(df, df.index[8], 'LONG')
    # باید از swing_low ایندکس 2 استفاده شود، نه ایندکس 9
    assert res['stop_loss'] == 98


def test_bos_candle_not_used_as_sl_swing():
    df = _make_risk_df('LONG')
    # اگر در کندل BOS یک swing_low هم باشد، نباید استفاده شود
    df.loc[df.index[8], 'swing_low'] = True
    df.loc[df.index[8], 'low'] = 100
    res = evaluate_risk(df, df.index[8], 'LONG')
    # باز هم باید از swing_low ایندکس 2 استفاده کند
    assert res['stop_loss'] == 98


def test_strategy_integration_long():
    # استفاده از fixture های فاز 7 برای تست integration
    from tests.test_phase7 import _make_5m_bullish_setup, _make_regime_df

    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res['signal'] == 'LONG'
    assert 'entry_price' in res
    assert 'stop_loss' in res
    assert 'take_profit' in res
    assert 'risk_reward' in res
    assert res['entry_price'] > res['stop_loss']  # LONG


def test_strategy_integration_short():
    from tests.test_phase7 import _make_5m_bearish_setup, _make_regime_df

    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup()
    res = strategy.generate_signal(df_4h, df_1h, df_5m)
    assert res['signal'] == 'SHORT'
    assert 'entry_price' in res
    assert 'stop_loss' in res
    assert 'take_profit' in res
    assert 'risk_reward' in res
    assert res['entry_price'] < res['stop_loss']  # SHORT
