import pytest
import math
from position_sizing import calculate_position_size
from portfolio_manager import PortfolioManager


def test_position_sizing_sl_1pct():
    res = calculate_position_size(1000, 0.01, 100, 99, allocation=0.25, max_leverage=20)
    assert res["valid"]
    assert res["margin_allocation"] == 250
    assert res["risk_amount"] == 10
    assert res["leverage"] == pytest.approx(4)
    assert res["notional_position_value"] == pytest.approx(1000)
    assert res["position_size"] == pytest.approx(10)


def test_position_sizing_sl_2pct():
    res = calculate_position_size(1000, 0.01, 100, 98, allocation=0.25, max_leverage=20)
    assert res["valid"]
    assert res["leverage"] == pytest.approx(2)
    assert res["notional_position_value"] == pytest.approx(500)


def test_position_sizing_sl_05pct():
    res = calculate_position_size(1000, 0.01, 100, 99.5, allocation=0.25, max_leverage=20)
    assert res["valid"]
    assert res["leverage"] == pytest.approx(8)
    assert res["notional_position_value"] == pytest.approx(2000)


def test_position_sizing_reject_high_leverage():
    res = calculate_position_size(1000, 0.01, 100, 99.9, allocation=0.25, max_leverage=20)
    assert not res["valid"]
    assert "exceeds" in res["reason"]


def test_position_sizing_reject_invalid_stop():
    res = calculate_position_size(1000, 0.01, 100, 100, allocation=0.25, max_leverage=20)
    assert not res["valid"]


def test_risk_remains_1pct_account():
    res = calculate_position_size(1000, 0.01, 100, 99, allocation=0.25, max_leverage=20)
    assert res["risk_amount"] == 10
    assert res["margin_allocation"] == 250


def test_portfolio_max_positions():
    pm = PortfolioManager(max_positions=4)
    assert pm.available_slots() == 4
    pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})
    assert pm.available_slots() == 3
    assert pm.is_symbol_open("BTC/USDT:USDT")
    pm.remove_position("BTC/USDT:USDT")
    assert pm.available_slots() == 4


def test_portfolio_same_symbol_rejected():
    pm = PortfolioManager(max_positions=4)
    pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})
    with pytest.raises(RuntimeError):
        pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})


def test_portfolio_filter_best_per_symbol():
    cands = [
        {"symbol": "BTC/USDT:USDT", "score": 80},
        {"symbol": "BTC/USDT:USDT", "score": 90},
    ]
    pm = PortfolioManager(max_positions=4)
    best = pm.filter_best_per_symbol(cands)
    assert len(best) == 1
    assert best[0]["score"] == 90


def test_select_top_candidates_respects_capacity():
    pm = PortfolioManager(max_positions=4)
    pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})
    cands = [
        {
            "symbol": "ETH/USDT:USDT",
            "score": 80,
            "valid": True,
            "signal": "LONG",
            "entry_price": 100,
            "stop_loss": 90,
            "take_profit": 120,
            "risk_reward": 2.0,
            "volume_24h_usdt": 2000000,
            "regime_4h": "BULLISH",
            "regime_1h": "BULLISH",
            "rsi_recovery": True,
            "choch": True,
            "bos": True,
            "risk_amount": 10,
            "position_size": 1,
        },
        {
            "symbol": "SOL/USDT:USDT",
            "score": 70,
            "valid": True,
            "signal": "LONG",
            "entry_price": 100,
            "stop_loss": 90,
            "take_profit": 120,
            "risk_reward": 2.0,
            "volume_24h_usdt": 2000000,
            "regime_4h": "BULLISH",
            "regime_1h": "BULLISH",
            "rsi_recovery": True,
            "choch": True,
            "bos": True,
            "risk_amount": 10,
            "position_size": 1,
        },
    ]
    selected = pm.select_top_candidates(cands)
    assert len(selected) == 2   # فقط ۲ کاندید موجود است؛ نه ۳
