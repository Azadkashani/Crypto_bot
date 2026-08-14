import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import config
from position_sizing import calculate_position_size
import strategy


def _make_position_sizing_result(account_balance, risk_per_trade, entry, sl, allocation, max_leverage):
    """محاسبه Position Sizing مستقیم با فرمول جدید."""
    return calculate_position_size(
        account_balance=account_balance,
        risk_per_trade=risk_per_trade,
        entry_price=entry,
        stop_loss=sl,
        allocation=allocation,
        max_leverage=max_leverage,
    )


def test_risk_amount_calculation():
    result = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 20)
    assert result["valid"] is True
    assert result["risk_amount"] == 10.0


def test_position_size_long():
    result = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 20)
    assert result["valid"] is True
    assert result["stop_distance"] == 5
    # با فرمول داینامیک: notional=200 و position_size=2.0
    assert result["position_size"] == pytest.approx(2.0)
    assert result["position_value"] == pytest.approx(200.0)
    assert result["margin_allocation"] == 250
    assert result["leverage"] == pytest.approx(0.8)


def test_position_size_short():
    result = _make_position_sizing_result(1000, 0.01, 100, 105, 0.25, 20)
    assert result["valid"] is True
    assert result["stop_distance"] == 5
    assert result["position_size"] == pytest.approx(2.0)
    assert result["leverage"] == pytest.approx(0.8)


def test_position_value():
    result = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 20)
    assert result["valid"] is True
    assert result["position_value"] == pytest.approx(200.0)


def test_margin_required():
    result = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 20)
    assert result["valid"] is True
    # margin_required = allocation = 250
    assert result["margin_required"] == 250.0


def test_leverage_does_not_change_risk_amount():
    result_5x = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 5)
    result_20x = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 20)
    assert result_5x["valid"] is True
    assert result_20x["valid"] is True
    assert result_5x["risk_amount"] == result_20x["risk_amount"] == 10.0
    assert result_5x["margin_required"] == result_20x["margin_required"] == 250.0


def test_invalid_account_balance():
    result = _make_position_sizing_result(0, 0.01, 100, 95, 0.25, 20)
    assert result["valid"] is False
    assert "Account balance" in result["reason"]


def test_invalid_risk_percentage():
    result = _make_position_sizing_result(1000, 1.5, 100, 95, 0.25, 20)
    assert result["valid"] is False


def test_entry_equals_stop():
    result = _make_position_sizing_result(1000, 0.01, 100, 100, 0.25, 20)
    assert result["valid"] is False
    assert "Entry price equals stop loss" in result["reason"]


def test_invalid_leverage():
    result = _make_position_sizing_result(1000, 0.01, 100, 95, 0.25, 0)
    assert result["valid"] is False
    assert "Leverage" in result["reason"] or "Max leverage" in result["reason"]


# -------------------------------------------------------------------
# Integration tests
# -------------------------------------------------------------------
def test_strategy_integration_long():
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

    entry = res["entry_price"]
    stop = res["stop_loss"]
    risk_amount = config.ACCOUNT_BALANCE * config.RISK_PER_TRADE
    stop_distance = abs(entry - stop)
    stop_distance_pct = stop_distance / entry
    margin_allocation = config.ACCOUNT_BALANCE * config.POSITION_ALLOCATION
    expected_leverage = risk_amount / (margin_allocation * stop_distance_pct)
    expected_notional = margin_allocation * expected_leverage
    expected_position_size = expected_notional / entry
    expected_position_value = expected_position_size * entry
    expected_margin_required = margin_allocation

    assert res["risk_amount"] == risk_amount
    assert res["stop_distance"] == stop_distance
    assert res["leverage"] == pytest.approx(expected_leverage)
    assert res["position_size"] == pytest.approx(expected_position_size)
    assert res["position_value"] == pytest.approx(expected_position_value)
    assert res["margin_required"] == pytest.approx(expected_margin_required)


def test_strategy_integration_short():
    from tests.test_phase7 import _make_5m_bearish_setup, _make_regime_df

    df_4h = _make_regime_df('bearish')
    df_1h = _make_regime_df('bearish')
    df_5m = _make_5m_bearish_setup()

    res = strategy.generate_signal(df_4h, df_1h, df_5m)

    assert res["signal"] == "SHORT"
    assert res["valid"] is True
    assert "risk_amount" in res
    assert "stop_distance" in res
    assert "position_size" in res
    assert "position_value" in res
    assert "margin_required" in res
    assert "leverage" in res

    entry = res["entry_price"]
    stop = res["stop_loss"]
    risk_amount = config.ACCOUNT_BALANCE * config.RISK_PER_TRADE
    stop_distance = abs(entry - stop)
    stop_distance_pct = stop_distance / entry
    margin_allocation = config.ACCOUNT_BALANCE * config.POSITION_ALLOCATION
    expected_leverage = risk_amount / (margin_allocation * stop_distance_pct)
    expected_notional = margin_allocation * expected_leverage
    expected_position_size = expected_notional / entry
    expected_position_value = expected_position_size * entry

    assert res["risk_amount"] == risk_amount
    assert res["stop_distance"] == stop_distance
    assert res["leverage"] == pytest.approx(expected_leverage)
    assert res["position_size"] == pytest.approx(expected_position_size)
    assert res["position_value"] == pytest.approx(expected_position_value)
    assert res["margin_required"] == pytest.approx(margin_allocation)


def test_no_future_data_in_position_sizing():
    from tests.test_phase7 import _make_5m_bullish_setup, _make_regime_df

    df_4h = _make_regime_df('bullish')
    df_1h = _make_regime_df('bullish')
    df_5m_full = _make_5m_bullish_setup()

    bos_idx = df_5m_full.index[44]
    df_5m_partial = df_5m_full.loc[:bos_idx]

    res_partial = strategy.generate_signal(df_4h, df_1h, df_5m_partial)
    res_full = strategy.generate_signal(df_4h, df_1h, df_5m_full)

    assert res_partial["signal"] == "LONG"
    assert res_full["signal"] == "LONG"
    assert res_partial["entry_price"] == res_full["entry_price"]
    assert res_partial["stop_loss"] == res_full["stop_loss"]
    assert res_partial["position_size"] == res_full["position_size"]
    assert res_partial["margin_required"] == res_full["margin_required"]