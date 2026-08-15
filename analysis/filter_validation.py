"""
V4 — اعتبارسنجی فیلترهای Candidate به روش chronological (بدون shuffle).

این ماژول فقط Validation انجام می‌دهد و هیچ تغییری در Strategy ایجاد نمی‌کند.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Callable, Optional, Tuple, Union
import json


# ----------------------------------------------------------------------
# توابع کمکی محاسبه معیارها
# ----------------------------------------------------------------------
def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """محاسبهٔ معیارهای اصلی از لیست معاملات."""
    if not rows:
        return {
            "total_trades": 0,
            "sl_count": 0,
            "tp_count": 0,
            "sl_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "avg_r": 0.0,
            "expectancy": 0.0,
            "profit_factor": float("inf"),
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "avg_mae": np.nan,
            "avg_mfe": np.nan,
        }

    total = len(rows)
    sl_count = sum(1 for r in rows if r.get("exit_reason") == "SL")
    tp_count = sum(1 for r in rows if r.get("exit_reason") == "TP")
    sl_rate = sl_count / total if total else 0.0

    pnl_values = [r.get("pnl", 0.0) for r in rows]
    r_values = [r.get("r_multiple", 0.0) for r in rows]
    total_pnl = sum(pnl_values)
    avg_pnl = total_pnl / total if total else 0.0
    avg_r = sum(r_values) / total if total else 0.0

    gross_profit = sum(p for p in pnl_values if p > 0)
    gross_loss = abs(sum(p for p in pnl_values if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    wins = [r for r in r_values if r > 0]
    losses = [r for r in r_values if r < 0]
    win_rate = len(wins) / total if total else 0.0
    avg_win_r = sum(wins) / len(wins) if wins else 0.0
    avg_loss_r = abs(sum(losses)) / len(losses) if losses else 0.0
    expectancy = win_rate * avg_win_r - (1 - win_rate) * avg_loss_r

    mae_vals = [r.get("mae_pct") for r in rows if r.get("mae_pct") is not None and not np.isnan(r.get("mae_pct"))]
    mfe_vals = [r.get("mfe_pct") for r in rows if r.get("mfe_pct") is not None and not np.isnan(r.get("mfe_pct"))]

    return {
        "total_trades": total,
        "sl_count": sl_count,
        "tp_count": tp_count,
        "sl_rate": sl_rate,
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "avg_r": avg_r,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "avg_mae": float(np.mean(mae_vals)) if mae_vals else np.nan,
        "avg_mfe": float(np.mean(mfe_vals)) if mfe_vals else np.nan,
    }


def apply_filter(rows: List[Dict[str, Any]], condition: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
    """فیلتر کردن معاملات بر اساس شرط."""
    return [r for r in rows if condition(r)]


def chronological_split(rows: List[Dict[str, Any]], train_ratio: float = 0.6, val_ratio: float = 0.2):
    """تقسیم chronological بدون shuffle."""
    if not rows:
        return [], [], []

    sorted_rows = sorted(rows, key=lambda r: pd.Timestamp(r.get("entry_time")))

    n = len(sorted_rows)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train = sorted_rows[:train_end]
    val = sorted_rows[train_end:val_end]
    oos = sorted_rows[val_end:]

    return train, val, oos


# ----------------------------------------------------------------------
# فیلترهای کاندید
# ----------------------------------------------------------------------
CANDIDATE_FILTERS: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "SL/ATR <= 2.0": lambda r: r.get("sl_atr_ratio", np.nan) <= 2.0,
    "SL/ATR <= 2.5": lambda r: r.get("sl_atr_ratio", np.nan) <= 2.5,
    "SL/ATR <= 3.0": lambda r: r.get("sl_atr_ratio", np.nan) <= 3.0,
    "SL/ATR <= 3.5": lambda r: r.get("sl_atr_ratio", np.nan) <= 3.5,
    "SL/ATR <= 4.0": lambda r: r.get("sl_atr_ratio", np.nan) <= 4.0,
    "LONG RSI <= 40": lambda r: r.get("direction") != "LONG" or r.get("rsi_entry", np.nan) <= 40,
    "LONG RSI <= 45": lambda r: r.get("direction") != "LONG" or r.get("rsi_entry", np.nan) <= 45,
    "LONG RSI <= 50": lambda r: r.get("direction") != "LONG" or r.get("rsi_entry", np.nan) <= 50,
    "SHORT RSI >= 50": lambda r: r.get("direction") != "SHORT" or r.get("rsi_entry", np.nan) >= 50,
    "SHORT RSI >= 55": lambda r: r.get("direction") != "SHORT" or r.get("rsi_entry", np.nan) >= 55,
    "SHORT RSI >= 60": lambda r: r.get("direction") != "SHORT" or r.get("rsi_entry", np.nan) >= 60,
    "Resistance distance >= 0.004": lambda r: r.get("direction") != "LONG" or r.get("distance_to_resistance", np.nan) >= 0.004,
    "Resistance distance >= 0.005": lambda r: r.get("direction") != "LONG" or r.get("distance_to_resistance", np.nan) >= 0.005,
    "Support distance >= 0.003": lambda r: r.get("direction") != "SHORT" or r.get("distance_to_support", np.nan) >= 0.003,
    "Support distance >= 0.004": lambda r: r.get("direction") != "SHORT" or r.get("distance_to_support", np.nan) >= 0.004,
}


COMBINATION_FILTERS: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "SL/ATR <= 3.0": CANDIDATE_FILTERS["SL/ATR <= 3.0"],
    "SL/ATR <= 3.0 + LONG RSI <= 45": lambda r: CANDIDATE_FILTERS["SL/ATR <= 3.0"](r) and CANDIDATE_FILTERS["LONG RSI <= 45"](r),
    "SL/ATR <= 3.0 + LONG RSI <= 45 + SHORT RSI >= 55": lambda r: (
        CANDIDATE_FILTERS["SL/ATR <= 3.0"](r)
        and CANDIDATE_FILTERS["LONG RSI <= 45"](r)
        and CANDIDATE_FILTERS["SHORT RSI >= 55"](r)
    ),
    "SL/ATR <= 3.0 + resistance distance >= 0.005": lambda r: (
        CANDIDATE_FILTERS["SL/ATR <= 3.0"](r)
        and CANDIDATE_FILTERS["Resistance distance >= 0.005"](r)
    ),
    "SL/ATR <= 3.0 + support distance >= 0.004": lambda r: (
        CANDIDATE_FILTERS["SL/ATR <= 3.0"](r)
        and CANDIDATE_FILTERS["Support distance >= 0.004"](r)
    ),
    "SL/ATR <= 3.0 + LONG RSI <= 45 + resistance distance >= 0.005": lambda r: (
        CANDIDATE_FILTERS["SL/ATR <= 3.0"](r)
        and CANDIDATE_FILTERS["LONG RSI <= 45"](r)
        and CANDIDATE_FILTERS["Resistance distance >= 0.005"](r)
    ),
    "SL/ATR <= 3.0 + LONG RSI <= 45 + support distance >= 0.004": lambda r: (
        CANDIDATE_FILTERS["SL/ATR <= 3.0"](r)
        and CANDIDATE_FILTERS["LONG RSI <= 45"](r)
        and CANDIDATE_FILTERS["Support distance >= 0.004"](r)
    ),
}


# ----------------------------------------------------------------------
# تحلیل اعتبارسنجی فیلتر
# ----------------------------------------------------------------------
def validate_filter(
    rows: List[Dict[str, Any]],
    filter_name: str,
    condition: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    """
    بررسی یک فیلتر روی Train/Validation/OOS.
    """
    train, val, oos = chronological_split(rows)

    # Baseline برای هر دوره
    baseline_all = summarize_rows(rows)
    baseline_train = summarize_rows(train)
    baseline_val = summarize_rows(val)
    baseline_oos = summarize_rows(oos)

    # فیلترشده برای هر دوره
    filt_train = apply_filter(train, condition)
    filt_val = apply_filter(val, condition)
    filt_oos = apply_filter(oos, condition)

    filt_all = apply_filter(rows, condition)

    metrics = {
        "filter": filter_name,
        # کل
        "all_trades": len(filt_all),
        "trade_retention_pct": len(filt_all) / len(rows) * 100 if rows else 0.0,
        "removed_sl": baseline_all["sl_count"] - summarize_rows(filt_all)["sl_count"],
        "removed_tp": baseline_all["tp_count"] - summarize_rows(filt_all)["tp_count"],
        "sl_removal_pct": (baseline_all["sl_count"] - summarize_rows(filt_all)["sl_count"]) / baseline_all["sl_count"] * 100 if baseline_all["sl_count"] else 0.0,
        "tp_removal_pct": (baseline_all["tp_count"] - summarize_rows(filt_all)["tp_count"]) / baseline_all["tp_count"] * 100 if baseline_all["tp_count"] else 0.0,
        # Train
        "train_trades": len(filt_train),
        "train_expectancy": summarize_rows(filt_train)["expectancy"],
        "train_pf": summarize_rows(filt_train)["profit_factor"],
        "train_sl_rate": summarize_rows(filt_train)["sl_rate"],
        # Validation
        "val_trades": len(filt_val),
        "val_expectancy": summarize_rows(filt_val)["expectancy"],
        "val_pf": summarize_rows(filt_val)["profit_factor"],
        "val_sl_rate": summarize_rows(filt_val)["sl_rate"],
        # OOS
        "oos_trades": len(filt_oos),
        "oos_expectancy": summarize_rows(filt_oos)["expectancy"],
        "oos_pf": summarize_rows(filt_oos)["profit_factor"],
        "oos_sl_rate": summarize_rows(filt_oos)["sl_rate"],
        # تغییرات نسبت به baseline
        "train_exp_change": summarize_rows(filt_train)["expectancy"] - baseline_train["expectancy"],
        "val_exp_change": summarize_rows(filt_val)["expectancy"] - baseline_val["expectancy"],
        "oos_exp_change": summarize_rows(filt_oos)["expectancy"] - baseline_oos["expectancy"],
        "train_pf_change": summarize_rows(filt_train)["profit_factor"] - baseline_train["profit_factor"],
        "val_pf_change": summarize_rows(filt_val)["profit_factor"] - baseline_val["profit_factor"],
        "oos_pf_change": summarize_rows(filt_oos)["profit_factor"] - baseline_oos["profit_factor"],
    }
    return metrics


def calculate_robustness_score(metrics: Dict[str, Any]) -> float:
    """
    امتیاز Robustness از 0 تا 100.

    عوامل:
    - بهبود OOS Expectancy
    - بهبود OOS PF
    - حفظ تعداد معاملات (trade retention)
    - کاهش SL بیشتر از TP
    - پایداری بین Train/Validation/OOS
    """
    score = 0.0

    # OOS Expectancy improvement: حداکثر 30 امتیاز
    if not np.isnan(metrics["oos_exp_change"]):
        score += max(0, min(30, metrics["oos_exp_change"] * 100))

    # OOS PF improvement: حداکثر 20 امتیاز
    if not np.isnan(metrics["oos_pf_change"]) and metrics["oos_pf_change"] != float('inf'):
        score += max(0, min(20, metrics["oos_pf_change"] * 20))

    # Trade retention: 50-90% ایده‌آل
    retention = metrics["trade_retention_pct"]
    if 50 <= retention <= 90:
        score += 20
    elif retention > 90:
        score += 10
    elif retention >= 30:
        score += 5

    # کاهش SL بیشتر از TP: حداکثر 20 امتیاز
    removed_sl = metrics.get("removed_sl", 0)
    removed_tp = metrics.get("removed_tp", 0)
    if removed_sl > removed_tp:
        score += min(20, (removed_sl - removed_tp) * 2)

    # پایداری بین دوره‌ها: حداکثر 10 امتیاز
    changes = [
        metrics["train_exp_change"],
        metrics["val_exp_change"],
        metrics["oos_exp_change"],
    ]
    if all(not np.isnan(c) for c in changes):
        sign_consistent = all(c >= 0 for c in changes) or all(c <= 0 for c in changes)
        if sign_consistent:
            score += 10
        elif metrics["oos_exp_change"] > 0:
            score += 5

    return max(0.0, min(100.0, score))


def determine_verdict(metrics: Dict[str, Any], score: float) -> str:
    """تعیین Verdict بر اساس امتیاز و OOS."""
    if score >= 70 and metrics["oos_exp_change"] > 0 and metrics["oos_trades"] >= 10:
        return "STRONG"
    elif score >= 50 and metrics["oos_exp_change"] >= 0:
        return "MODERATE"
    elif score >= 30:
        return "WEAK"
    else:
        return "REJECT"


def detect_overfitting(metrics: Dict[str, Any]) -> str:
    """شناسایی Overfitting."""
    train_imp = metrics.get("train_exp_change", 0)
    oos_imp = metrics.get("oos_exp_change", 0)

    if train_imp > 0 and oos_imp < 0:
        return "OVERFIT: Train positive, OOS negative"
    if train_imp > 2 * max(0, oos_imp):
        return "OVERFIT: Train improvement much larger than OOS"
    if metrics.get("oos_trades", 0) < 10:
        return "LOW_TRADE_COUNT: OOS sample too small"
    return "OK"


# ----------------------------------------------------------------------
# Sensitivity Analysis
# ----------------------------------------------------------------------
def sensitivity_sl_atr(rows: List[Dict[str, Any]], thresholds: List[float]) -> pd.DataFrame:
    """جدول حساسیت برای SL/ATR."""
    results = []
    for th in thresholds:
        condition = lambda r: r.get("sl_atr_ratio", np.nan) <= th
        m = validate_filter(rows, f"SL/ATR <= {th}", condition)
        results.append({
            "threshold": th,
            "train_expectancy": m["train_expectancy"],
            "val_expectancy": m["val_expectancy"],
            "oos_expectancy": m["oos_expectancy"],
            "train_pf": m["train_pf"],
            "val_pf": m["val_pf"],
            "oos_pf": m["oos_pf"],
            "all_trades": m["all_trades"],
            "trade_retention_pct": m["trade_retention_pct"],
            "oos_sl_rate": m["oos_sl_rate"],
        })
    return pd.DataFrame(results)


def sensitivity_rsi(rows: List[Dict[str, Any]], thresholds: List[float], direction: str) -> pd.DataFrame:
    """جدول حساسیت برای RSI در جهت مشخص."""
    results = []
    for th in thresholds:
        if direction == "LONG":
            condition = lambda r: r.get("direction") != "LONG" or r.get("rsi_entry", np.nan) <= th
        else:
            condition = lambda r: r.get("direction") != "SHORT" or r.get("rsi_entry", np.nan) >= th
        m = validate_filter(rows, f"{direction} RSI {th}", condition)
        results.append({
            "threshold": th,
            "train_expectancy": m["train_expectancy"],
            "val_expectancy": m["val_expectancy"],
            "oos_expectancy": m["oos_expectancy"],
            "train_pf": m["train_pf"],
            "val_pf": m["val_pf"],
            "oos_pf": m["oos_pf"],
            "all_trades": m["all_trades"],
            "trade_retention_pct": m["trade_retention_pct"],
            "oos_sl_rate": m["oos_sl_rate"],
        })
    return pd.DataFrame(results)
