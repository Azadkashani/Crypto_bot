# tests/test_phase11.py

import pytest
from metrics import calculate_metrics


# ---------- ابزارهای کمکی ----------

def _trade(pnl, r_multiple=None, risk_amount=10.0):
    """ساخت دیکشنری معامله تستی."""
    if r_multiple is None:
        r_multiple = pnl / risk_amount if risk_amount else 0.0
    return {
        "direction": "LONG" if pnl >= 0 else "SHORT",
        "entry_time": "2025-01-01 00:00:00+00:00",
        "entry_price": 100.0,
        "stop_loss": 95.0 if pnl >= 0 else 105.0,
        "take_profit": 110.0 if pnl >= 0 else 90.0,
        "position_size": 1.0,
        "risk_amount": risk_amount,
        "exit_time": "2025-01-01 01:00:00+00:00",
        "exit_price": 110.0 if pnl >= 0 else 90.0,
        "exit_reason": "TP" if pnl > 0 else ("SL" if pnl < 0 else "BE"),
        "pnl": pnl,
        "r_multiple": r_multiple,
    }


def _equity(points):
    """ساخت منحنی سرمایه از لیست (timestamp, balance)."""
    return [{"timestamp": ts, "balance": bal} for ts, bal in points]


# ---------- تست‌ها ----------

def test_empty_trades():
    result = calculate_metrics([], [], initial_balance=1000)
    assert result["total_trades"] == 0
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 0
    assert result["breakeven_trades"] == 0
    assert result["win_rate"] == 0.0
    assert result["loss_rate"] == 0.0
    assert result["gross_profit"] == 0.0
    assert result["gross_loss"] == 0.0
    assert result["net_profit"] == 0.0
    assert result["profit_factor"] == float('inf')
    assert result["average_r"] == 0.0
    assert result["max_drawdown"] == 0.0
    assert result["max_drawdown_pct"] == 0.0
    assert result["peak_balance"] == 1000.0
    assert result["final_balance"] == 1000.0


def test_empty_equity_curve():
    trades = [_trade(10, 1.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [], initial_balance=1000)
    assert result["total_trades"] == 2
    assert result["net_profit"] == 5.0
    assert result["final_balance"] == 1005.0
    assert result["peak_balance"] == 1000.0
    assert result["max_drawdown"] == 0.0


def test_all_winning_trades():
    trades = [_trade(10, 1.0), _trade(20, 2.0)]
    result = calculate_metrics(trades, [], initial_balance=1000)
    assert result["winning_trades"] == 2
    assert result["losing_trades"] == 0
    assert result["win_rate"] == 1.0
    assert result["loss_rate"] == 0.0
    assert result["gross_profit"] == 30.0
    assert result["gross_loss"] == 0.0
    assert result["profit_factor"] == float('inf')


def test_all_losing_trades():
    trades = [_trade(-10, -1.0), _trade(-20, -2.0)]
    result = calculate_metrics(trades, [], initial_balance=1000)
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 2
    assert result["win_rate"] == 0.0
    assert result["loss_rate"] == 1.0
    assert result["gross_profit"] == 0.0
    assert result["gross_loss"] == 30.0
    assert result["profit_factor"] == 0.0


def test_all_breakeven_trades():
    trades = [_trade(0, 0.0), _trade(0, 0.0)]
    result = calculate_metrics(trades, [], initial_balance=1000)
    assert result["breakeven_trades"] == 2
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 0
    assert result["win_rate"] == 0.0
    assert result["loss_rate"] == 0.0


def test_mixed_win_loss_breakeven():
    trades = [
        _trade(10, 1.0),
        _trade(-5, -0.5),
        _trade(0, 0.0),
        _trade(20, 2.0),
        _trade(-10, -1.0),
    ]
    result = calculate_metrics(trades, [], initial_balance=1000)
    assert result["winning_trades"] == 2
    assert result["losing_trades"] == 2
    assert result["breakeven_trades"] == 1
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["loss_rate"] == pytest.approx(0.5)


def test_win_rate_explicit():
    trades = [_trade(10, 1.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["win_rate"] == pytest.approx(0.5)


def test_loss_rate_explicit():
    trades = [_trade(10, 1.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["loss_rate"] == pytest.approx(0.5)


def test_gross_profit():
    trades = [_trade(10, 1.0), _trade(20, 2.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["gross_profit"] == 30.0


def test_gross_loss():
    trades = [_trade(10, 1.0), _trade(-5, -0.5), _trade(-10, -1.0)]
    result = calculate_metrics(trades, [])
    assert result["gross_loss"] == 15.0


def test_net_profit():
    trades = [_trade(10, 1.0), _trade(-4, -0.4)]
    result = calculate_metrics(trades, [], initial_balance=100)
    assert result["net_profit"] == 6.0
    assert result["final_balance"] == 106.0


def test_profit_factor_zero_loss():
    trades = [_trade(10, 1.0)]
    result = calculate_metrics(trades, [])
    assert result["profit_factor"] == float('inf')


def test_average_r():
    trades = [_trade(10, 1.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["average_r"] == pytest.approx(0.25)


def test_average_win_r():
    trades = [_trade(10, 1.0), _trade(20, 2.0), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["average_win_r"] == pytest.approx(1.5)


def test_average_loss_r():
    trades = [_trade(10, 1.0), _trade(-5, -0.5), _trade(-10, -1.0)]
    result = calculate_metrics(trades, [])
    assert result["average_loss_r"] == pytest.approx(0.75)


def test_expectancy():
    trades = [
        _trade(10, 1.0),
        _trade(20, 2.0),
        _trade(-5, -0.5),
        _trade(-10, -1.0),
    ]
    result = calculate_metrics(trades, [])
    expected = 0.5 * 1.5 - 0.5 * 0.75
    assert result["expectancy"] == pytest.approx(expected)


def test_largest_win():
    trades = [_trade(10, 1.0), _trade(25, 2.5), _trade(-5, -0.5)]
    result = calculate_metrics(trades, [])
    assert result["largest_win"] == 25.0


def test_largest_loss():
    trades = [_trade(10, 1.0), _trade(-5, -0.5), _trade(-15, -1.5)]
    result = calculate_metrics(trades, [])
    assert result["largest_loss"] == -15.0


def test_max_drawdown():
    equity = _equity([
        ("2025-01-01", 1000.0),
        ("2025-01-02", 1200.0),
        ("2025-01-03", 900.0),
        ("2025-01-04", 1100.0),
    ])
    result = calculate_metrics([], equity, initial_balance=1000)
    assert result["max_drawdown"] == pytest.approx(0.25)
    assert result["max_drawdown_pct"] == pytest.approx(25.0)


def test_max_drawdown_percentage():
    equity = _equity([
        ("2025-01-01", 1000.0),
        ("2025-01-02", 800.0),
        ("2025-01-03", 1000.0),
    ])
    result = calculate_metrics([], equity)
    assert result["max_drawdown"] == pytest.approx(0.2)
    assert result["max_drawdown_pct"] == pytest.approx(20.0)


def test_peak_balance():
    equity = _equity([("a", 100), ("b", 150), ("c", 120)])
    result = calculate_metrics([], equity)
    assert result["peak_balance"] == 150.0


def test_final_balance():
    equity = _equity([("a", 100), ("b", 150), ("c", 120)])
    result = calculate_metrics([], equity)
    assert result["final_balance"] == 120.0


def test_max_consecutive_wins():
    trades = [
        _trade(10, 1.0),
        _trade(20, 2.0),
        _trade(-5, -0.5),
        _trade(15, 1.5),
        _trade(-10, -1.0),
        _trade(-20, -2.0),
    ]
    result = calculate_metrics(trades, [])
    assert result["max_consecutive_wins"] == 2


def test_max_consecutive_losses():
    trades = [
        _trade(10, 1.0),
        _trade(-5, -0.5),
        _trade(-10, -1.0),
        _trade(5, 0.5),
        _trade(-20, -2.0),
    ]
    result = calculate_metrics(trades, [])
    assert result["max_consecutive_losses"] == 2


def test_breakeven_reset_streaks():
    trades = [
        _trade(10, 1.0),
        _trade(10, 1.0),
        _trade(0, 0.0),
        _trade(10, 1.0),
        _trade(-10, -1.0),
        _trade(-10, -1.0),
    ]
    result = calculate_metrics(trades, [])
    assert result["max_consecutive_wins"] == 2
    assert result["max_consecutive_losses"] == 2


def test_recovery_factor():
    equity = _equity([
        ("a", 1000.0),
        ("b", 900.0),
        ("c", 1100.0),
    ])
    trades = [_trade(100, 1.0)]
    result = calculate_metrics(trades, equity, initial_balance=1000)
    assert result["recovery_factor"] == pytest.approx(1.0)


def test_division_by_zero_safety():
    result = calculate_metrics([_trade(10, 1.0)], [])
    assert result["profit_factor"] == float('inf')

    result2 = calculate_metrics([_trade(-10, -1.0)], [])
    assert result2["recovery_factor"] == 0.0


def test_no_mutation_trades():
    trades = [_trade(10, 1.0), _trade(-5, -0.5)]
    original = [t.copy() for t in trades]
    calculate_metrics(trades, [])
    assert trades == original


def test_no_mutation_equity_curve():
    equity = _equity([("a", 100), ("b", 150)])
    original = [e.copy() for e in equity]
    calculate_metrics([], equity)
    assert equity == original


def test_realistic_mixed_scenario():
    trades = [
        _trade(50, 1.0),
        _trade(-30, -0.6),
        _trade(20, 0.4),
        _trade(0, 0.0),
        _trade(-40, -0.8),
        _trade(60, 1.2),
    ]
    equity = _equity([
        ("2025-01-01", 1000.0),
        ("2025-01-02", 1050.0),
        ("2025-01-03", 1020.0),
        ("2025-01-04", 1040.0),
        ("2025-01-05", 1040.0),
        ("2025-01-06", 1000.0),
        ("2025-01-07", 1060.0),
    ])
    result = calculate_metrics(trades, equity, initial_balance=1000)

    assert result["total_trades"] == 6
    assert result["winning_trades"] == 3
    assert result["losing_trades"] == 2
    assert result["breakeven_trades"] == 1
    assert result["gross_profit"] == 130.0
    assert result["gross_loss"] == 70.0
    assert result["net_profit"] == 60.0
    assert result["profit_factor"] == pytest.approx(130 / 70)
    assert result["average_r"] == pytest.approx((1.0 - 0.6 + 0.4 + 0.0 - 0.8 + 1.2) / 6)
    assert result["average_win_r"] == pytest.approx((1.0 + 0.4 + 1.2) / 3)
    assert result["average_loss_r"] == pytest.approx((0.6 + 0.8) / 2)
    assert result["win_rate"] == pytest.approx(3 / 5)
    assert result["loss_rate"] == pytest.approx(2 / 5)
    assert result["expectancy"] == pytest.approx(
        (3 / 5) * ((1.0 + 0.4 + 1.2) / 3) - (2 / 5) * ((0.6 + 0.8) / 2)
    )
    assert result["largest_win"] == 60.0
    assert result["largest_loss"] == -40.0
    assert result["peak_balance"] == 1060.0
    assert result["final_balance"] == 1060.0
    assert result["max_drawdown"] == pytest.approx(50 / 1050)
    assert result["max_drawdown_pct"] == pytest.approx((50 / 1050) * 100)
    assert result["max_consecutive_wins"] == 1
    assert result["max_consecutive_losses"] == 1
    assert result["recovery_factor"] == pytest.approx(60 / 50)
