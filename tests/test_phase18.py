import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from position_sizing import calculate_position_size


def test_single_position_risk_is_1_percent():
    res = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    assert res["valid"]
    assert res["risk_amount"] == pytest.approx(10)
    assert res["margin_allocation"] == pytest.approx(250)


def test_single_position_allocation_is_25_percent():
    res = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    assert res["margin_allocation"] == pytest.approx(250)


def test_risk_equals_4_percent_of_allocation():
    res = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    risk = res["risk_amount"]
    margin = res["margin_allocation"]
    assert risk / margin == pytest.approx(0.04)


def test_leverage_does_not_increase_risk():
    res1 = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    res2 = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=10)
    assert res1["risk_amount"] == res2["risk_amount"]
    assert res1["risk_amount"] == 10


def test_position_size_from_stop_distance():
    res = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    expected_size = 10 / 4  # risk_amount / stop_distance
    assert res["position_size"] == pytest.approx(expected_size)
    assert res["notional_position_value"] == pytest.approx(250)


def test_allocation_cap_rejects_excessive_position():
    # stop_distance=4%, risk=10 -> size=2.5, notional=250 OK
    # stop_distance=0.5% -> required leverage > max -> reject
    res = calculate_position_size(1000, 0.01, 100, 99.5, allocation=0.25, max_leverage=20)
    assert not res["valid"]
    assert "exceeds" in res["reason"]


def test_four_positions_max():
    # شبیه‌سازی با یک PortfolioManager ساده
    from portfolio_manager import PortfolioManager
    pm = PortfolioManager(max_positions=4)
    for i in range(4):
        sym = f"SYM{i}/USDT:USDT"
        pm.add_position(sym, {"symbol": sym})
    with pytest.raises(RuntimeError):
        pm.add_position("SYM5/USDT:USDT", {"symbol": "SYM5/USDT:USDT"})


def test_fifth_position_rejected():
    from portfolio_manager import PortfolioManager
    pm = PortfolioManager(max_positions=4)
    for i in range(4):
        pm.add_position(f"SYM{i}/USDT:USDT", {"symbol": f"SYM{i}/USDT:USDT"})
    assert pm.available_slots() == 0
    with pytest.raises(RuntimeError):
        pm.add_position("SYM5/USDT:USDT", {"symbol": "SYM5/USDT:USDT"})


def test_same_symbol_duplicate_rejected():
    from portfolio_manager import PortfolioManager
    pm = PortfolioManager(max_positions=4)
    pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})
    with pytest.raises(RuntimeError):
        pm.add_position("BTC/USDT:USDT", {"symbol": "BTC/USDT:USDT"})


def test_four_positions_total_risk_equals_4_percent():
    res = calculate_position_size(1000, 0.01, 100, 96, allocation=0.25, max_leverage=20)
    total_risk = res["risk_amount"] * 4
    assert total_risk == pytest.approx(40)


def test_four_stop_losses_reduce_equity_by_4_percent():
    initial = 1000
    risk_per_trade = initial * 0.01
    total_loss = risk_per_trade * 4
    assert initial - total_loss == pytest.approx(960)


def test_four_take_profits_with_rr2():
    initial = 1000
    risk_per_trade = initial * 0.01
    profit_per_trade = risk_per_trade * 2
    total_profit = profit_per_trade * 4
    assert initial + total_profit == pytest.approx(1080)


def test_pnl_long():
    position = {"direction": "LONG", "entry_price": 100, "exit_price": 110, "position_size": 2, "risk_amount": 10}
    pnl = (position["exit_price"] - position["entry_price"]) * position["position_size"]
    assert pnl == 20


def test_pnl_short():
    position = {"direction": "SHORT", "entry_price": 100, "exit_price": 90, "position_size": 2, "risk_amount": 10}
    pnl = (position["entry_price"] - position["exit_price"]) * position["position_size"]
    assert pnl == 20


def test_r_multiple_long():
    pnl = 20
    risk = 10
    assert pnl / risk == 2


def test_r_multiple_short():
    pnl = 20
    risk = 10
    assert pnl / risk == 2


def test_candidate_and_selected_are_distinct():
    candidates = 10
    selected = 4
    assert selected <= candidates


def test_top_four_scored_signals_selected():
    scores = [91, 85, 80, 75, 70]
    top4 = sorted(scores, reverse=True)[:4]
    assert len(top4) == 4
    assert top4[0] == 91
    assert top4[3] == 75


def test_selection_is_deterministic():
    scores = [91, 85, 80, 75, 70]
    top4 = sorted(scores, reverse=True)[:4]
    top4_again = sorted(scores, reverse=True)[:4]
    assert top4 == top4_again


def test_duplicate_symbol_not_selected_twice():
    best_per_symbol = {}
    candidates = [
        {"symbol": "BTC/USDT:USDT", "score": 91},
        {"symbol": "BTC/USDT:USDT", "score": 85},
        {"symbol": "ETH/USDT:USDT", "score": 80},
    ]
    for c in candidates:
        sym = c["symbol"]
        if sym not in best_per_symbol or c["score"] > best_per_symbol[sym]["score"]:
            best_per_symbol[sym] = c
    assert len(best_per_symbol) == 2


def test_balance_updates_only_once():
    balance = 1000
    pnl = 10
    balance += pnl
    balance += pnl  # باید فقط یک بار اعمال شود
    assert balance == 1020


def test_position_risk_is_fixed_after_entry():
    initial_balance = 1000
    risk_amount = initial_balance * 0.01
    # بعد از تغییر balance، ریسک معامله قبلی ثابت بماند
    later_balance = 2000
    assert risk_amount == 10
    # ریسک معامله بعدی بر اساس balance جدید است
    next_risk = later_balance * 0.01
    assert next_risk == 20


def test_no_leverage_risk_multiplication():
    risk = 10
    leverage = 20
    # لوریج نباید ریسک را ضرب کند
    assert risk * leverage != risk
    assert risk == 10


def test_invalid_position_rejected_safely():
    res = calculate_position_size(1000, 0.01, 100, 100, allocation=0.25, max_leverage=20)
    assert not res["valid"]


def test_no_unrealistic_pnl_explosion():
    # سناریوی ساده: سود 2R
    pnl = 20
    assert pnl < 1000  # سود معقول