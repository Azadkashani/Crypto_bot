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
        # بدون منحنی سرمایه، دراودان صفر است
        peak_balance = float(initial_balance) if initial_balance is not None else 0.0
        final_balance = peak_balance + total_pnl if initial_balance is not None else total_pnl
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
