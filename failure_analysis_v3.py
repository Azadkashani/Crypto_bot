"""
ماژول تحلیل V3 — Counterfactual و Threshold Analysis برای کاهش SL.

این ماژول فقط تحلیل آماری انجام می‌دهد و هیچ تغییری در Strategy، Entry،
Exit، SL، TP یا Risk Management اعمال نمی‌کند.
"""

from __future__ import annotations

import os
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Callable, Optional, Tuple

import config


# ----------------------------------------------------------------------
# توابع کمکی محاسبهٔ خلاصهٔ معاملات
# ----------------------------------------------------------------------
def summarize_trades(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """محاسبهٔ معیارهای اصلی از لیست معاملات."""
    if not rows:
        return {
            "total_trades": 0,
            "sl_count": 0,
            "tp_count": 0,
            "sl_rate": 0.0,
            "tp_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "avg_r": 0.0,
            "profit_factor": float("inf"),
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "expectancy": 0.0,
            "avg_mae": np.nan,
            "avg_mfe": np.nan,
        }

    total = len(rows)
    sl_count = sum(1 for r in rows if r.get("exit_reason") == "SL")
    tp_count = sum(1 for r in rows if r.get("exit_reason") == "TP")
    sl_rate = sl_count / total if total else 0.0
    tp_rate = tp_count / total if total else 0.0

    pnl_values = [r.get("pnl", 0.0) for r in rows]
    r_values = [r.get("r_multiple", 0.0) for r in rows]
    total_pnl = sum(pnl_values)
    avg_pnl = total_pnl / total if total else 0.0
    avg_r = sum(r_values) / total if total else 0.0

    gross_profit = sum(p for p in pnl_values if p > 0)
    gross_loss = abs(sum(p for p in pnl_values if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectancy از R-Multiple
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
        "tp_rate": tp_rate,
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "avg_r": avg_r,
        "profit_factor": profit_factor,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "expectancy": expectancy,
        "avg_mae": float(np.mean(mae_vals)) if mae_vals else np.nan,
        "avg_mfe": float(np.mean(mfe_vals)) if mfe_vals else np.nan,
    }


def calculate_filter_effect(baseline: Dict[str, Any], filtered_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """مقایسهٔ فیلتر با Baseline."""
    filt = summarize_trades(filtered_rows)

    removed_total = baseline["total_trades"] - filt["total_trades"]
    removed_sl = baseline["sl_count"] - filt["sl_count"]
    removed_tp = baseline["tp_count"] - filt["tp_count"]
    sl_removal_pct = removed_sl / baseline["sl_count"] * 100 if baseline["sl_count"] else 0.0
    tp_removal_pct = removed_tp / baseline["tp_count"] * 100 if baseline["tp_count"] else 0.0

    pnl_change = filt["total_pnl"] - baseline["total_pnl"]
    expectancy_change = filt["expectancy"] - baseline["expectancy"]
    pf_change = filt["profit_factor"] - baseline["profit_factor"]
    # Drawdown تغییر نمی‌تواند به‌سادگی محاسبه شود؛ اینجا skip
    return {
        "filter": filt,
        "removed_total": removed_total,
        "removed_sl": removed_sl,
        "removed_tp": removed_tp,
        "sl_removal_pct": sl_removal_pct,
        "tp_removal_pct": tp_removal_pct,
        "pnl_change": pnl_change,
        "expectancy_change": expectancy_change,
        "pf_change": pf_change,
    }


def filter_rows(rows: List[Dict[str, Any]], condition: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
    return [r for r in rows if condition(r)]


# ----------------------------------------------------------------------
# Sweep Thresholds
# ----------------------------------------------------------------------
def sweep_rsi(rows: List[Dict[str, Any]], direction: str, thresholds: List[float]) -> List[Dict[str, Any]]:
    results = []
    for th in thresholds:
        if direction == "LONG":
            condition = lambda r: r["direction"] == "SHORT" or r.get("rsi_entry", np.nan) <= th
        else:
            condition = lambda r: r["direction"] == "LONG" or r.get("rsi_entry", np.nan) >= th
        filtered = filter_rows(rows, condition)
        effect = calculate_filter_effect(summarize_trades(rows), filtered)
        effect["threshold"] = f"{'<=' if direction=='LONG' else '>='} {th}"
        effect["direction"] = direction
        results.append(effect)
    return results


def sweep_sl_atr(rows: List[Dict[str, Any]], thresholds: List[float], mode: str = "max") -> List[Dict[str, Any]]:
    results = []
    for th in thresholds:
        if mode == "max":
            condition = lambda r: r.get("sl_atr_ratio", np.nan) <= th
        else:
            condition = lambda r: r.get("sl_atr_ratio", np.nan) >= th
        filtered = filter_rows(rows, condition)
        effect = calculate_filter_effect(summarize_trades(rows), filtered)
        effect["threshold"] = f"{'<=' if mode=='max' else '>='} {th}"
        results.append(effect)
    return results


def sweep_distance(rows: List[Dict[str, Any]], direction: str, thresholds: List[float]) -> List[Dict[str, Any]]:
    results = []
    for th in thresholds:
        if direction == "LONG":
            condition = lambda r: r["direction"] == "SHORT" or r.get("distance_to_resistance", np.nan) >= th
        else:
            condition = lambda r: r["direction"] == "LONG" or r.get("distance_to_support", np.nan) >= th
        filtered = filter_rows(rows, condition)
        effect = calculate_filter_effect(summarize_trades(rows), filtered)
        effect["threshold"] = f">= {th}"
        effect["direction"] = direction
        results.append(effect)
    return results


def sweep_volume_ratio(rows: List[Dict[str, Any]], thresholds: List[float]) -> List[Dict[str, Any]]:
    results = []
    for th in thresholds:
        condition = lambda r: r.get("volume_ratio", np.nan) >= th
        filtered = filter_rows(rows, condition)
        effect = calculate_filter_effect(summarize_trades(rows), filtered)
        effect["threshold"] = f">= {th}"
        results.append(effect)
    return results


# ----------------------------------------------------------------------
# ترکیب‌های چندعاملی
# ----------------------------------------------------------------------
def analyze_combinations(rows: List[Dict[str, Any]], baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    combs = {
        "RSI_late + SL_wide": lambda r: r["failure_reasons"] and ("RSI_ENTRY_TOO_LATE" in r["failure_reasons"] and "SL_TOO_WIDE" in r["failure_reasons"]),
        "RSI_late + res_close": lambda r: r["failure_reasons"] and ("RSI_ENTRY_TOO_LATE" in r["failure_reasons"] and "ENTRY_TOO_CLOSE_TO_RESISTANCE" in r["failure_reasons"]),
        "RSI_late + sup_close": lambda r: r["failure_reasons"] and ("RSI_ENTRY_TOO_LATE" in r["failure_reasons"] and "ENTRY_TOO_CLOSE_TO_SUPPORT" in r["failure_reasons"]),
        "SL_wide + res_close": lambda r: r["failure_reasons"] and ("SL_TOO_WIDE" in r["failure_reasons"] and "ENTRY_TOO_CLOSE_TO_RESISTANCE" in r["failure_reasons"]),
        "SL_wide + sup_close": lambda r: r["failure_reasons"] and ("SL_TOO_WIDE" in r["failure_reasons"] and "ENTRY_TOO_CLOSE_TO_SUPPORT" in r["failure_reasons"]),
    }
    results = []
    for name, cond in combs.items():
        subset = [r for r in rows if cond(r)]
        if not subset:
            continue
        summary = summarize_trades(subset)
        results.append({
            "combination": name,
            **summary,
        })
    return results


def temporal_stability(rows: List[Dict[str, Any]], filter_cond: Callable[[Dict[str, Any]], bool], n_periods: int = 4) -> List[Dict[str, Any]]:
    """بررسی پایداری فیلتر در بازه‌های زمانی."""
    if not rows:
        return []
    # مرتب‌سازی زمانی و تقسیم به n_periods
    sorted_rows = sorted(rows, key=lambda r: pd.Timestamp(r["entry_time"]))
    chunk_size = max(1, len(sorted_rows) // n_periods)
    periods = [sorted_rows[i:i+chunk_size] for i in range(0, len(sorted_rows), chunk_size)]

    results = []
    for i, period in enumerate(periods, 1):
        total = summarize_trades(period)
        filtered = summarize_trades(filter_rows(period, filter_cond))
        results.append({
            "period": i,
            "total_before": total["total_trades"],
            "total_after": filtered["total_trades"],
            "sl_rate_before": total["sl_rate"],
            "sl_rate_after": filtered["sl_rate"],
            "expectancy_before": total["expectancy"],
            "expectancy_after": filtered["expectancy"],
        })
    return results


def symbol_analysis(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    symbols = sorted(set(r.get("symbol", "?") for r in rows))
    result = {}
    for sym in symbols:
        subset = [r for r in rows if r.get("symbol") == sym]
        result[sym] = summarize_trades(subset)
    return result


def direction_analysis(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    long = [r for r in rows if r.get("direction") == "LONG"]
    short = [r for r in rows if r.get("direction") == "SHORT"]
    return {
        "LONG": summarize_trades(long),
        "SHORT": summarize_trades(short),
    }


# ----------------------------------------------------------------------
# تحلیل ATR Bucket
# ----------------------------------------------------------------------
def atr_bucket_analysis(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # استفاده از ATR% به‌صورت atr_entry / entry_price
    for r in rows:
        if r.get("atr_entry") and r.get("entry_price"):
            r["atr_pct"] = r["atr_entry"] / r["entry_price"]
        else:
            r["atr_pct"] = np.nan

    buckets = {
        "Low Volatility": lambda p: p < 0.001,
        "Medium Volatility": lambda p: 0.001 <= p < 0.002,
        "High Volatility": lambda p: 0.002 <= p < 0.004,
        "Very High Volatility": lambda p: p >= 0.004,
    }
    results = []
    for name, cond in buckets.items():
        subset = [r for r in rows if not np.isnan(r.get("atr_pct", np.nan)) and cond(r["atr_pct"])]
        if subset:
            summary = summarize_trades(subset)
            results.append({
                "bucket": name,
                **summary,
                "avg_atr_pct": float(np.mean([r["atr_pct"] for r in subset])),
            })
    return results
