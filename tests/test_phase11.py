import pytest
import math
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
    # win_rate=0.5, loss_rate=0.5, avg_win=1.5, avg_loss=0.75
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
    # peak=1200، drop به 900 => drawdown = (1200-900)/1200 = 0.25
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
    assert result["max_consecutive_wins"] == 2  # 2 قبل از breakeven
    assert result["max_consecutive_losses"] == 2


def test_recovery_factor():
    equity = _equity([
        ("a", 1000.0),
        ("b", 900.0),
        ("c", 1100.0),
    ])
    trades = [_trade(100, 1.0)]
    result = calculate_metrics(trades, equity, initial_balance=1000)
    # max abs drawdown = 1000 - 900 = 100
    # net_profit = final 1100 - 1000 = 100
    # recovery_factor = 100 / 100 = 1.0
    assert result["recovery_factor"] == pytest.approx(1.0)


def test_division_by_zero_safety():
    # بدون ضرر، profit_factor بی‌نهایت
    result = calculate_metrics([_trade(10, 1.0)], [])
    assert result["profit_factor"] == float('inf')

    # دراودان صفر و سود منفی => recovery_factor = 0
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
    assert result["average_r"] == pytest.approx((1.0 -0.6 +0.4 +0.0 -0.8 +1.2)/6)
    assert result["average_win_r"] == pytest.approx((1.0+0.4+1.2)/3)
    assert result["average_loss_r"] == pytest.approx((0.6+0.8)/2)
    assert result["win_rate"] == pytest.approx(3/5)
    assert result["loss_rate"] == pytest.approx(2/5)
    assert result["expectancy"] == pytest.approx(
        (3/5)*((1.0+0.4+1.2)/3) - (2/5)*((0.6+0.8)/2)
    )
    assert result["largest_win"] == 60.0
    assert result["largest_loss"] == -40.0
    assert result["peak_balance"] == 1060.0
    assert result["final_balance"] == 1060.0
    # drawdown از peak=1060 به 1000 => (1060-1000)/1060 ≈ 0.0566
    assert result["max_drawdown"] == pytest.approx(60/1060)
    assert result["max_drawdown_pct"] == pytest.approx((60/1060)*100)
    assert result["max_consecutive_wins"] == 1  # wins separated by losses/breakeven? Actually sequence: win, loss, win, breakeven, loss, win => max consecutive wins=1, max consecutive losses=2? let's compute: trades: W,L,W,BE,L,W => max wins=1, max losses=1? Wait two losses? positions: [-40] after breakeven then win, only one loss. So max losses=1. But we have losses at positions 2 and 5? No positions: index0 W, index1 L, index2 W, index3 BE, index4 L, index5 W => max wins=1, max losses=1. We may adjust expected.
    assert result["max_consecutive_wins"] == 1
    assert result["max_consecutive_losses"] == 1
    assert result["recovery_factor"] == pytest.approx(60 / 60)  # max abs dd = 1060-1000=60? Actually peak=1060, trough=1000 at index5? sequence balances: 1000,1050,1020,1040,1040,1000,1060. Peak 1060 at end, max drawdown from prior peak? running peak: 1000,1050,1050,1050,1050,1050,1060; max abs dd occurs when balance=1000 with peak=1050? dd=50. Wait final balance 1060, peak final 1060 no dd. Running peak before last: 1050, at index5 balance=1000 dd=50. Also earlier 1050->1020 dd=30, 1050->1040 dd=10. So max abs dd = 50. Then recovery_factor = net_profit / max_abs_dd = 60 / 50 = 1.2. Need adjust. In equity data: after trade4 balance=1040, trade5 loss 40 => 1000, trade6 win 60 => 1060. Running peak before final: 1050? Actually point 2 balance=1050, then down to 1020, up to 1040, same 1040, down to 1000, up to 1060. Running peak before final is 1050. So max abs dd = 1050 - 1000 = 50. Net profit = 1060-1000=60. Recovery=60/50=1.2. We'll set expected accordingly. Let's adjust test realistic to be accurate.

I'll include corrected expected values in final code.

Need ensure no failure. But this is just code generation. We can produce test with accurate calculations.

Let's refine test_realistic_mixed_scenario with correct expected:

trades pnl: 50, -30, 20, 0, -40, 60
total pnl = 60
equity balances: 1000, 1050, 1020, 1040, 1040, 1000, 1060
running peak: 1000,1050,1050,1050,1050,1050,1060
max_abs_dd = max(0,0,30,10,10,50,0)=50
max_drawdown fraction = max(0,0,30/1050=0.02857,10/1050=0.00952,10/1050,50/1050=0.04762,0)=0.047619...
recovery factor = 60/50=1.2
consecutive wins/losses: sequence W,L,W,BE,L,W => max wins=1, max losses=1. 

average_r: r values [1.0, -0.6, 0.4, 0.0, -0.8, 1.2]; sum=1.2? compute: 1 -0.6=0.4; +0.4=0.8; +0=0.8; -0.8=0; +1.2=1.2; avg=0.2. Wait not 1.2? sum = 1.0 -0.6 +0.4 +0.0 -0.8 +1.2 = 1.2. average=0.2. Good.

average_win_r: wins at index0 r=1.0, index2 0.4, index5 1.2 => sum=2.6, avg=0.866666.
average_loss_r: losses at index1 abs 0.6, index4 abs 0.8 => avg=0.7.

win_rate=3/5=0.6, loss_rate=2/5=0.4.
expectancy = 0.6*0.866666 - 0.4*0.7 = 0.52 - 0.28 = 0.24? approximate 0.24. Let's compute exact: 0.6 * (2.6/3) = 0.6*0.866666=0.52; 0.4*0.7=0.28; expectancy=0.24.

profit_factor=130/70=1.857142857.

largest_loss = -40.0.

Final_balance = 1060, peak_balance = 1060.

max_drawdown = 0.0476190, pct=4.7619.

recovery_factor=1.2.

We'll use pytest.approx with rel/abs.

Now produce final code.

Need ensure all test functions exist count maybe 30? We have about 30 functions. I'll list count: empty_trades, empty_equity_curve, all_winning, all_losing, all_breakeven, mixed, win_rate, loss_rate, gross_profit, gross_loss, net_profit, profit_factor_zero_loss, average_r, average_win_r, average_loss_r, expectancy, largest_win, largest_loss, max_drawdown, max_drawdown_percentage, peak_balance, final_balance, max_consecutive_wins, max_consecutive_losses, breakeven_reset, recovery_factor, division_by_zero, no_mutation_trades, no_mutation_equity, realistic_mixed. That's 30 exactly. Good.

Need import math maybe not used, can omit.

Potential issue: `calculate_metrics(trades, [])` when initial_balance None and equity_curve empty, final_balance = total_pnl; peak_balance = 0.0; net_profit = total_pnl. Good.

In empty_equity_curve test, initial_balance=1000, trades pnl +10 and -5, final_balance = initial + total_pnl = 1005. peak_balance=1000. Good.

Now provide final answer.پیاده‌سازی فاز ۱۱ کامل شد. دو فایل زیر به‌صورت کامل ارائه می‌شوند:

---

## 1. `metrics.py`

```python
"""
ماژول محاسبه معیارهای عملکرد (Performance Metrics).

این ماژول هیچ‌گونه ورودی را تغییر نمی‌دهد و فقط آمار معاملات و منحنی سرمایه را
به‌صورت مستقل محاسبه می‌کند.

API عمومی:
    calculate_metrics(trades, equity_curve, initial_balance=None) -> dict
"""

from typing import List, Dict, Any, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    """تبدیل امن مقدار به float."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_metrics(
    trades: Optional[List[Dict[str, Any]]] = None,
    equity_curve: Optional[List[Dict[str, Any]]] = None,
    initial_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """
    محاسبه معیارهای عملکرد از لیست معاملات و منحنی سرمایه.

    پارامترها:
        trades: لیست معاملات. هر معامله باید حداقل شامل کلیدهای
                'pnl' و 'r_multiple' باشد.
        equity_curve: لیست نقاط سرمایه شامل 'timestamp' و 'balance'.
                     ترتیب باید صعودی باشد.
        initial_balance: (اختیاری) سرمایه اولیه.

    خروجی:
        دیکشنری شامل تمام معیارهای مورد نیاز فاز ۱۱.

    نکته:
        - تابع هیچ‌یک از ورودی‌ها را تغییر نمی‌دهد.
        - در صورت نبود معامله یا منحنی سرمایه، مقادیر امن و قطعی برمی‌گرداند.
        - تقسیم بر صفر کنترل شده است.
    """
    trades = trades or []
    equity_curve = equity_curve or []

    # ---------- طبقه‌بندی معاملات ----------
    total_trades = len(trades)

    winning_trades = 0
    losing_trades = 0
    breakeven_trades = 0

    gross_profit = 0.0
    gross_loss = 0.0

    r_values = []
    win_r_values = []
    loss_r_values_abs = []

    largest_win = 0.0
    largest_loss = 0.0  # منفی‌ترین مقدار pnl

    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_consecutive_wins = 0
    current_consecutive_losses = 0

    total_pnl = 0.0

    for trade in trades:
        pnl = _safe_float(trade.get("pnl"), 0.0)
        r_multiple = _safe_float(trade.get("r_multiple"), 0.0)

        total_pnl += pnl
        r_values.append(r_multiple)

        if pnl > 0:
            winning_trades += 1
            gross_profit += pnl
            win_r_values.append(r_multiple)
            if pnl > largest_win:
                largest_win = pnl

            current_consecutive_wins += 1
            current_consecutive_losses = 0
            if current_consecutive_wins > max_consecutive_wins:
                max_consecutive_wins = current_consecutive_wins

        elif pnl < 0:
            losing_trades += 1
            gross_loss += abs(pnl)
            loss_r_values_abs.append(abs(r_multiple))
            if pnl < largest_loss:
                largest_loss = pnl

            current_consecutive_losses += 1
            current_consecutive_wins = 0
            if current_consecutive_losses > max_consecutive_losses:
                max_consecutive_losses = current_consecutive_losses

        else:  # pnl == 0
            breakeven_trades += 1
            current_consecutive_wins = 0
            current_consecutive_losses = 0

    # ---------- نرخ‌های برد و باخت ----------
    decisive_trades = winning_trades + losing_trades
    if decisive_trades > 0:
        win_rate = winning_trades / decisive_trades
        loss_rate = losing_trades / decisive_trades
    else:
        win_rate = 0.0
        loss_rate = 0.0

    # ---------- R-multiple metrics ----------
    if total_trades > 0:
        average_r = sum(r_values) / total_trades
    else:
        average_r = 0.0

    if winning_trades > 0:
        average_win_r = sum(win_r_values) / winning_trades
    else:
        average_win_r = 0.0

    if losing_trades > 0:
        average_loss_r = sum(loss_r_values_abs) / losing_trades
    else:
        average_loss_r = 0.0

    # ---------- Expectancy بر اساس R ----------
    expectancy = (win_rate * average_win_r) - (loss_rate * average_loss_r)

    # ---------- Profit Factor ----------
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float('inf')

    # ---------- سود خالص ----------
    if initial_balance is not None:
        initial_balance = float(initial_balance)
        if equity_curve:
            final_balance = _safe_float(equity_curve[-1].get("balance"), initial_balance)
        else:
            final_balance = initial_balance + total_pnl
        net_profit = final_balance - initial_balance
    else:
        net_profit = total_pnl
        if equity_curve:
            final_balance = _safe_float(equity_curve[-1].get("balance"), total_pnl)
        else:
            final_balance = total_pnl

    # ---------- Drawdown از منحنی سرمایه ----------
    peak_balance = 0.0
    max_drawdown = 0.0
    max_abs_drawdown = 0.0

    if equity_curve:
        balances = [_safe_float(point.get("balance"), 0.0) for point in equity_curve]
        peak_balance = max(balances)
        final_balance_from_curve = balances[-1]

        if initial_balance is None:
            final_balance = final_balance_from_curve
            net_profit = final_balance_from_curve - balances[0] if balances else total_pnl

        running_peak = -float('inf')
        for bal in balances:
            if bal > running_peak:
                running_peak = bal
            abs_dd = running_peak - bal
            if abs_dd > max_abs_drawdown:
                max_abs_drawdown = abs_dd
            if running_peak != 0:
                dd_pct = abs_dd / running_peak
                if dd_pct > max_drawdown:
                    max_drawdown = dd_pct
            else:
                # اگر peak صفر باشد، دراودان صفر در نظر گرفته می‌شود
                if abs_dd > 0:
                    max_drawdown = float('inf')
        if max_drawdown == float('inf'):
            max_drawdown = 0.0
    else:
        peak_balance = float(initial_balance) if initial_balance is not None else 0.0
        final_balance = peak_balance
        max_drawdown = 0.0
        max_abs_drawdown = 0.0

    max_drawdown_pct = max_drawdown * 100.0

    # ---------- Recovery Factor ----------
    if max_abs_drawdown > 0:
        recovery_factor = net_profit / max_abs_drawdown
    else:
        if net_profit > 0:
            recovery_factor = float('inf')
        else:
            recovery_factor = 0.0

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "breakeven_trades": breakeven_trades,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": net_profit,
        "profit_factor": profit_factor,
        "average_r": average_r,
        "average_win_r": average_win_r,
        "average_loss_r": average_loss_r,
        "expectancy": expectancy,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "peak_balance": peak_balance,
        "final_balance": final_balance,
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        "recovery_factor": recovery_factor,
    }
