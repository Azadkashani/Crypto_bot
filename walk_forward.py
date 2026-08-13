"""
ماژول اعتبارسنجی Walk-Forward برای استراتژی معاملاتی.

این ماژول بدون تغییر منطق استراتژی، عملکرد آن را روی پنجره‌های زمانی
متوالی و غیرهمپوشان آزمایش می‌کند.

مدل پنجره:
    بازه آموزشی (تاریخی) به‌صورت expanding است.
    بازه اعتبارسنجی (test) به‌صورت غیرهمپوشان و به‌ترتیب زمانی جلو می‌رود.

مهم:
    داده‌های زمانی نباید به‌صورت تصادفی جابه‌جا شوند.
    ترتیب زمانی و استقلال تایم‌فریم‌ها حفظ می‌شود.
"""

from typing import List, Dict, Any, Optional
import pandas as pd

from backtest_engine import BacktestEngine
from metrics import calculate_metrics


def _validate_index(df: pd.DataFrame, name: str) -> None:
    """بررسی یکتایی و ترتیب صعودی ایندکس زمانی."""
    if df is None:
        raise ValueError(f"{name} cannot be None")
    if df.empty:
        return
    if not df.index.is_monotonic_increasing:
        raise ValueError(f"{name} timestamps must be sorted ascending")
    if df.index.duplicated().any():
        raise ValueError(f"{name} timestamps must be unique")


def generate_walk_forward_windows(
    n_candles: int,
    train_size: int,
    test_size: int,
    step_size: Optional[int] = None,
) -> List[Dict[str, int]]:
    """
    تولید پنجره‌های Walk-Forward با مدل expanding train.

    پارامترها:
        n_candles: تعداد کندل‌های ۵ دقیقه‌ای موجود.
        train_size: تعداد کندل اولیه برای بازه تاریخی/گرم‌کردن.
        test_size: تعداد کندل‌های هر بازه اعتبارسنجی.
        step_size: گام حرکت بازه اعتبارسنجی. اگر None باشد برابر test_size.

    خروجی:
        لیست دیکشنری شامل train_start, train_end, test_start, test_end.
    """
    if train_size <= 0:
        raise ValueError("train_size must be positive")
    if test_size <= 0:
        raise ValueError("test_size must be positive")
    if step_size is not None and step_size <= 0:
        raise ValueError("step_size must be positive")

    if step_size is None:
        step_size = test_size

    if n_candles < train_size + test_size:
        return []

    windows = []
    test_start = train_size
    window_number = 1

    while test_start < n_candles:
        test_end = min(test_start + test_size - 1, n_candles - 1)
        windows.append({
            "window_number": window_number,
            "train_start": 0,
            "train_end": test_start - 1,
            "test_start": test_start,
            "test_end": test_end,
        })
        window_number += 1
        test_start += step_size

    return windows


def run_walk_forward(
    data_5m: pd.DataFrame,
    data_1h: pd.DataFrame,
    data_4h: pd.DataFrame,
    train_size: int,
    test_size: int,
    step_size: Optional[int] = None,
    initial_balance: float = 1000.0,
) -> Dict[str, Any]:
    """
    اجرای Walk-Forward Validation روی داده‌های چندتایم‌فریمی.

    پارامترها:
        data_5m: دیتافریم ۵ دقیقه‌ای.
        data_1h: دیتافریم ۱ ساعته.
        data_4h: دیتافریم ۴ ساعته.
        train_size: تعداد کندل ۵ دقیقه‌ای برای بازه تاریخی اولیه.
        test_size: تعداد کندل ۵ دقیقه‌ای برای هر بازه اعتبارسنجی.
        step_size: گام حرکت بازه اعتبارسنجی.
        initial_balance: سرمایه اولیه برای هر بازه اعتبارسنجی.

    خروجی:
        دیکشنری شامل:
            - windows: لیست نتایج هر پنجره
            - aggregated: خلاصه تجمیعی نتایج
    """
    # اعتبارسنجی ایندکس‌ها
    _validate_index(data_5m, "data_5m")
    _validate_index(data_1h, "data_1h")
    _validate_index(data_4h, "data_4h")

    if train_size <= 0:
        raise ValueError("train_size must be positive")
    if test_size <= 0:
        raise ValueError("test_size must be positive")
    if step_size is not None and step_size <= 0:
        raise ValueError("step_size must be positive")

    n_5m = len(data_5m)
    windows = generate_walk_forward_windows(n_5m, train_size, test_size, step_size)

    if not windows:
        return {
            "windows": [],
            "aggregated": {
                "total_windows": 0,
                "total_trades": 0,
                "total_net_profit": 0.0,
                "average_window_return": 0.0,
                "average_win_rate": 0.0,
                "average_profit_factor": 0.0,
                "average_expectancy": 0.0,
                "worst_window_profit": 0.0,
                "best_window_profit": 0.0,
                "worst_window_drawdown": 0.0,
                "profitable_windows": 0,
                "losing_windows": 0,
                "profitable_window_ratio": 0.0,
            }
        }

    window_results = []

    for w in windows:
        test_start_time = data_5m.index[w["test_start"]]
        test_end_time = data_5m.index[w["test_end"]]

        # فقط داده تا انتهای بازه اعتبارسنجی برای جلوگیری از نشت آینده
        slice_5m = data_5m.iloc[: w["test_end"] + 1]
        slice_1h = data_1h.loc[data_1h.index <= test_end_time]
        slice_4h = data_4h.loc[data_4h.index <= test_end_time]

        engine = BacktestEngine(
            data_5m=slice_5m,
            data_1h=slice_1h,
            data_4h=slice_4h,
            initial_balance=initial_balance,
        )
        raw_result = engine.run()

        all_trades = raw_result.get("trades", [])

        # فقط معاملاتی که در بازه اعتبارسنجی شروع شده‌اند محاسبه می‌شوند
        validation_trades = [
            t for t in all_trades
            if t.get("entry_time") is not None
            and test_start_time <= t["entry_time"] <= test_end_time
        ]

        # ساخت منحنی سرمایه مختص بازه اعتبارسنجی
        balance = initial_balance
        equity_curve = []
        for trade in validation_trades:
            balance += trade.get("pnl", 0.0)
            equity_curve.append({
                "timestamp": trade.get("exit_time"),
                "balance": balance,
            })

        metrics = calculate_metrics(
            trades=validation_trades,
            equity_curve=equity_curve,
            initial_balance=initial_balance,
        )

        window_results.append({
            "window_number": w["window_number"],
            "train_start": data_5m.index[w["train_start"]],
            "train_end": data_5m.index[w["train_end"]],
            "test_start": test_start_time,
            "test_end": test_end_time,
            "test_candles": w["test_end"] - w["test_start"] + 1,
            **metrics,
        })

    # ---------- تجمیع نتایج ----------
    total_windows = len(window_results)
    total_trades = sum(r["total_trades"] for r in window_results)
    total_net_profit = sum(r["net_profit"] for r in window_results)
    average_window_return = total_net_profit / total_windows if total_windows > 0 else 0.0
    average_win_rate = (
        sum(r["win_rate"] for r in window_results) / total_windows
        if total_windows > 0 else 0.0
    )
    average_expectancy = (
        sum(r["expectancy"] for r in window_results) / total_windows
        if total_windows > 0 else 0.0
    )

    # میانگین Profit Factor: فقط مقادیر متناهی در نظر گرفته می‌شوند
    valid_pf = [
        r["profit_factor"] for r in window_results
        if r["profit_factor"] != float('inf')
    ]
    if not valid_pf:
        average_profit_factor = float('inf') if total_windows > 0 else 0.0
    else:
        average_profit_factor = sum(valid_pf) / len(valid_pf)

    worst_window_profit = min(r["net_profit"] for r in window_results)
    best_window_profit = max(r["net_profit"] for r in window_results)
    worst_window_drawdown = max(r["max_drawdown"] for r in window_results)

    profitable_windows = sum(1 for r in window_results if r["net_profit"] > 0)
    losing_windows = sum(1 for r in window_results if r["net_profit"] < 0)
    profitable_window_ratio = profitable_windows / total_windows if total_windows > 0 else 0.0

    aggregated = {
        "total_windows": total_windows,
        "total_trades": total_trades,
        "total_net_profit": total_net_profit,
        "average_window_return": average_window_return,
        "average_win_rate": average_win_rate,
        "average_profit_factor": average_profit_factor,
        "average_expectancy": average_expectancy,
        "worst_window_profit": worst_window_profit,
        "best_window_profit": best_window_profit,
        "worst_window_drawdown": worst_window_drawdown,
        "profitable_windows": profitable_windows,
        "losing_windows": losing_windows,
        "profitable_window_ratio": profitable_window_ratio,
    }

    return {
        "windows": window_results,
        "aggregated": aggregated,
    }
