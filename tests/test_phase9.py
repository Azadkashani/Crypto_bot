# tests/test_phase9.py
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import config
from position_sizing import calculate_position_size
import strategy

# ------------------------------------------------------------
# تست‌های Position Sizing
# ------------------------------------------------------------
def test_risk_amount_calculation():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is True
    assert result["risk_amount"] == 10.0

def test_position_size_long():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is True
    assert result["stop_distance"] == 5
    assert result["position_size"] == 2.0

def test_position_size_short():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=105,
        leverage=20,
    )
    assert result["valid"] is True
    assert result["stop_distance"] == 5
    assert result["position_size"] == 2.0

def test_position_value():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is True
    assert result["position_value"] == 200.0  # 2 * 100

def test_margin_required():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is True
    assert result["margin_required"] == 10.0  # 200 / 20

def test_leverage_does_not_change_risk_amount():
    result_5x = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=5,
    )
    result_20x = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result_5x["valid"] is True
    assert result_20x["valid"] is True
    assert result_5x["risk_amount"] == result_20x["risk_amount"] == 10.0
    assert result_5x["position_size"] == result_20x["position_size"] == 2.0
    # margin تغییر می‌کند
    assert result_5x["margin_required"] == 40.0  # 200/5
    assert result_20x["margin_required"] == 10.0

def test_invalid_account_balance():
    result = calculate_position_size(
        account_balance=0,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is False
    assert "Account balance" in result["reason"]

def test_invalid_risk_percentage():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=1.5,  # بیش از 1
        entry_price=100,
        stop_loss=95,
        leverage=20,
    )
    assert result["valid"] is False

def test_entry_equals_stop():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=100,
        leverage=20,
    )
    assert result["valid"] is False
    assert "Entry price equals stop loss" in result["reason"]

def test_invalid_leverage():
    result = calculate_position_size(
        account_balance=1000,
        risk_per_trade=0.01,
        entry_price=100,
        stop_loss=95,
        leverage=0,
    )
    assert result["valid"] is False
    assert "Leverage" in result["reason"]

# ------------------------------------------------------------
# تست‌های یکپارچگی با strategy.py
# ------------------------------------------------------------
def test_strategy_integration_long():
    # استفاده از fixture های فاز 7 برای ساخت سناریوی کامل
    from tests.test_phase7 import _make_5m_bullish_setup, _make_regime_df

    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m = _make_5m_bullish_setup()

    res = strategy.generate_signal(df_4h, df_1h, df_5m)

    assert res["signal"] == "LONG"
    assert res["valid"] is True
    assert "risk_amount" in res
    assert "stop_distance" in res
    assert "position_size" in res
    assert "position_value" in res
    assert "margin_required" in res
    assert "leverage" in res

    # بررسی مقادیر با محاسبه دستی
    entry = res["entry_price"]
    stop = res["stop_loss"]
    risk_amount = config.ACCOUNT_BALANCE * config.RISK_PER_TRADE
    stop_distance = abs(entry - stop)
    expected_position_size = risk_amount / stop_distance

    assert res["risk_amount"] == risk_amount
    assert res["stop_distance"] == stop_distance
    assert res["position_size"] == expected_position_size
    assert res["position_value"] == expected_position_size * entry
    assert res["margin_required"] == (expected_position_size * entry) / config.LEVERAGE

def test_strategy_integration_short():
    from tests.test_phase7 import _make_5m_bearish_setup, _make_regime_df

    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup()

    res = strategy.generate_signal(df_4h, df_1h, df_5m)

    assert res["signal"] == "SHORT"
    assert res["valid"] is True
    assert "risk_amount" in res
    assert "position_size" in res
    assert "margin_required" in res

def test_no_future_data_in_position_sizing():
    # Position sizing فقط از Entry و Stop Loss حاصل تا BOS استفاده می‌کند.
    # داده‌های بعد از BOS در خروجی تأثیری ندارند.
    from tests.test_phase7 import _make_5m_bullish_setup, _make_regime_df

    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m_full = _make_5m_bullish_setup()

    # شبیه‌سازی فقط تا لحظه BOS (ایندکس 44)
    bos_idx = df_5m_full.index[44]
    df_5m_partial = df_5m_full.loc[:bos_idx]

    res_partial = strategy.generate_signal(df_4h, df_1h, df_5m_partial)
    res_full = strategy.generate_signal(df_4h, df_1h, df_5m_full)

    # هر دو باید LONG باشند و مقادیر position sizing یکسان
    assert res_partial["signal"] == "LONG"
    assert res_full["signal"] == "LONG"
    assert res_partial["entry_price"] == res_full["entry_price"]
    assert res_partial["stop_loss"] == res_full["stop_loss"]
    assert res_partial["position_size"] == res_full["position_size"]
    assert res_partial["margin_required"] == res_full["margin_required"]
