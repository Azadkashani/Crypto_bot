"""
Walk-Forward Validation مخصوص SL/ATR.

این ماژول فقط برای تحلیل Robustness آستانه‌های SL/ATR است و هیچ تغییری
در استراتژی، ورود، خروج، SL/TP یا مدیریت ریسک ایجاد نمی‌کند.

روش:
    - تقسیم chronological معاملات بر اساس entry_time
    - استفاده از روش Expanding-Window
    - در هر پنجره:
        TRAIN: انتخاب آستانه بهینه بر اساس داده‌های گذشته
        VALIDATION: اعمال آستانه انتخاب‌شده و مقایسه با Baseline بدون فیلتر
"""

from __future__ import annotations

import os
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Callable, Optional, Tuple


CANDIDATE_THRESHOLDS = [2.0, 2.5, 3.0, 3.5, 4.0]


def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """محاسبه معیارهای اصلی از لیست معاملات."""
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
    }


def filter_by_sl_atr(rows: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """نگه‌داشتن معاملاتی که sl_atr_ratio <= threshold هستند."""
    return [r for r in rows if r.get("sl_atr_ratio") is not None and r["sl_atr_ratio"] <= threshold]


def select_threshold_from_train(train_rows: List[Dict[str, Any]], thresholds: List[float]) -> Optional[float]:
    """
    انتخاب آستانه از داده‌های TRAIN با قاعده‌ی محافظه‌کارانه.

    قوانین:
        1. حداقل 5 معامله بعد از فیلتر برای معتبر بودن
        2. expectancy مثبت
        3. ترجیح بالاترین expectancy؛ در صورت نزدیکی به‌هم،
           آستانه‌ی کمتر (محافظه‌کارانه‌تر) انتخاب شود.
    """
    best_threshold = None
    best_expectancy = -999.0

    for th in thresholds:
        filtered = filter_by_sl_atr(train_rows, th)
        if len(filtered) < 5:
            continue
        metrics = summarize_rows(filtered)
        exp = metrics["expectancy"]
        if exp > best_expectancy + 0.03:
            best_threshold = th
            best_expectancy = exp
        elif abs(exp - best_expectancy) <= 0.03:
            # اگر تفاوت خیلی کم بود، آستانه‌ی کمتر را ترجیح بده
            if best_threshold is None or th < best_threshold:
                best_threshold = th

    # اگر هیچ آستانه‌ای معتبر نبود، از بزرگ‌ترین آستانه با معامله کافی استفاده کن
    if best_threshold is None:
        for th in sorted(thresholds, reverse=True):
            filtered = filter_by_sl_atr(train_rows, th)
            if len(filtered) >= 5:
                best_threshold = th
                break

    return best_threshold


def run_walk_forward(
    rows: List[Dict[str, Any]],
    thresholds: List[float] = CANDIDATE_THRESHOLDS,
    initial_train_size: int = 40,
    validation_size: int = 20,
    output_dir: str = "analysis",
) -> Dict[str, Any]:
    """
    اجرای Walk-Forward Validation روی SL/ATR.
    """
    if not rows:
        return {
            "windows": [],
            "threshold_stats": {},
            "summary": {
                "number_of_windows": 0,
                "candidate_thresholds": thresholds,
                "baseline_total_pnl": 0.0,
                "baseline_expectancy": 0.0,
                "baseline_pf": float("inf"),
            }
        }

    # مرتب‌سازی chronological
    sorted_rows = sorted(rows, key=lambda r: pd.Timestamp(r.get("entry_time")))

    total = len(sorted_rows)
    windows: List[Dict[str, Any]] = []
    threshold_stats: Dict[float, Dict[str, Any]] = {}

    val_start_idx = initial_train_size

    while val_start_idx < total:
        val_end_idx = min(val_start_idx + validation_size - 1, total - 1)

        if val_start_idx >= total:
            break

        train_rows = sorted_rows[:val_start_idx]
        val_rows = sorted_rows[val_start_idx:val_end_idx + 1]

        if not train_rows or not val_rows:
            break

        train_dates = (
            pd.Timestamp(train_rows[0]["entry_time"]),
            pd.Timestamp(train_rows[-1]["entry_time"]),
        )
        val_dates = (
            pd.Timestamp(val_rows[0]["entry_time"]),
            pd.Timestamp(val_rows[-1]["entry_time"]),
        )

        # Baseline TRAIN
        train_baseline = summarize_rows(train_rows)
        # Baseline VALIDATION
        val_baseline = summarize_rows(val_rows)

        # انتخاب آستانه از TRAIN
        selected_threshold = select_threshold_from_train(train_rows, thresholds)

        # اعمال آستانه انتخاب‌شده روی TRAIN
        train_filtered_rows = filter_by_sl_atr(train_rows, selected_threshold) if selected_threshold else []
        train_filtered = summarize_rows(train_filtered_rows)

        # اعمال آستانه انتخاب‌شده روی VALIDATION
        val_filtered_rows = filter_by_sl_atr(val_rows, selected_threshold) if selected_threshold else []
        val_filtered = summarize_rows(val_filtered_rows)

        window = {
            "window_id": len(windows) + 1,
            "train_start": train_dates[0],
            "train_end": train_dates[1],
            "validation_start": val_dates[0],
            "validation_end": val_dates[1],
            "train_trades": len(train_rows),
            "validation_trades": len(val_rows),
            "selected_threshold": selected_threshold,
            "train_baseline_pnl": train_baseline["total_pnl"],
            "train_baseline_expectancy": train_baseline["expectancy"],
            "train_baseline_pf": train_baseline["profit_factor"],
            "train_filtered_trades": train_filtered["total_trades"],
            "train_filtered_sl": train_filtered["sl_count"],
            "train_filtered_tp": train_filtered["tp_count"],
            "train_filtered_pnl": train_filtered["total_pnl"],
            "train_filtered_expectancy": train_filtered["expectancy"],
            "train_filtered_pf": train_filtered["profit_factor"],
            "validation_baseline_trades": val_baseline["total_trades"],
            "validation_baseline_sl": val_baseline["sl_count"],
            "validation_baseline_tp": val_baseline["tp_count"],
            "validation_baseline_pnl": val_baseline["total_pnl"],
            "validation_baseline_expectancy": val_baseline["expectancy"],
            "validation_baseline_pf": val_baseline["profit_factor"],
            "validation_filtered_trades": val_filtered["total_trades"],
            "validation_filtered_sl": val_filtered["sl_count"],
            "validation_filtered_tp": val_filtered["tp_count"],
            "validation_filtered_pnl": val_filtered["total_pnl"],
            "validation_filtered_expectancy": val_filtered["expectancy"],
            "validation_filtered_pf": val_filtered["profit_factor"],
            "validation_pnl_delta": val_filtered["total_pnl"] - val_baseline["total_pnl"],
            "validation_expectancy_delta": val_filtered["expectancy"] - val_baseline["expectancy"],
            "validation_pf_delta": val_filtered["profit_factor"] - val_baseline["profit_factor"],
        }
        windows.append(window)

        # جمع‌آوری عملکرد هر آستانه در این پنجره
        for th in thresholds:
            filtered_train = filter_by_sl_atr(train_rows, th)
            filtered_val = filter_by_sl_atr(val_rows, th)
            train_metrics = summarize_rows(filtered_train)
            val_metrics = summarize_rows(filtered_val)

            if th not in threshold_stats:
                threshold_stats[th] = {
                    "times_selected": 0,
                    "positive_validation_windows": 0,
                    "total_validation_windows": 0,
                    "validation_expectancies": [],
                    "validation_pfs": [],
                    "validation_pnls": [],
                    "validation_trade_counts": [],
                }

            if selected_threshold == th:
                threshold_stats[th]["times_selected"] += 1
            threshold_stats[th]["total_validation_windows"] += 1
            if val_metrics["expectancy"] > 0:
                threshold_stats[th]["positive_validation_windows"] += 1
            threshold_stats[th]["validation_expectancies"].append(val_metrics["expectancy"])
            threshold_stats[th]["validation_pfs"].append(val_metrics["profit_factor"])
            threshold_stats[th]["validation_pnls"].append(val_metrics["total_pnl"])
            threshold_stats[th]["validation_trade_counts"].append(val_metrics["total_trades"])

        # حرکت به پنجره بعدی: train شامل validation قبلی می‌شود
        val_start_idx = val_end_idx + 1

    # ساخت CSV ها و گزارش
    os.makedirs(output_dir, exist_ok=True)

    windows_df = pd.DataFrame(windows)
    windows_df.to_csv(os.path.join(output_dir, "sl_atr_walk_forward.csv"), index=False)

    threshold_rows = []
    for th in thresholds:
        stats = threshold_stats.get(th, {})
        expectancies = stats.get("validation_expectancies", [])
        pfs = stats.get("validation_pfs", [])
        pnls = stats.get("validation_pnls", [])
        trades = stats.get("validation_trade_counts", [])
        threshold_rows.append({
            "threshold": th,
            "times_selected": stats.get("times_selected", 0),
            "selection_rate": stats.get("times_selected", 0) / len(windows) if windows else 0.0,
            "validation_windows_tested": stats.get("total_validation_windows", 0),
            "positive_validation_windows": stats.get("positive_validation_windows", 0),
            "positive_validation_rate": stats.get("positive_validation_windows", 0) / stats.get("total_validation_windows", 0) if stats.get("total_validation_windows", 0) else 0.0,
            "average_validation_expectancy": float(np.mean(expectancies)) if expectancies else 0.0,
            "median_validation_expectancy": float(np.median(expectancies)) if expectancies else 0.0,
            "average_validation_pf": float(np.mean(pfs)) if pfs else 0.0,
            "median_validation_pf": float(np.median(pfs)) if pfs else 0.0,
            "total_validation_pnl": float(sum(pnls)) if pnls else 0.0,
            "average_validation_pnl": float(np.mean(pnls)) if pnls else 0.0,
            "worst_validation_pnl": float(min(pnls)) if pnls else 0.0,
            "best_validation_pnl": float(max(pnls)) if pnls else 0.0,
            "average_trade_count": float(np.mean(trades)) if trades else 0.0,
            "minimum_trade_count": int(min(trades)) if trades else 0,
            "maximum_trade_count": int(max(trades)) if trades else 0,
        })
    threshold_df = pd.DataFrame(threshold_rows)
    threshold_df.to_csv(os.path.join(output_dir, "sl_atr_walk_forward_thresholds.csv"), index=False)

    # Baseline کلی
    baseline_all = summarize_rows(sorted_rows)

    # Summary JSON
    summary = {
        "number_of_windows": len(windows),
        "candidate_thresholds": thresholds,
        "baseline_total_pnl": baseline_all["total_pnl"],
        "baseline_expectancy": baseline_all["expectancy"],
        "baseline_pf": baseline_all["profit_factor"],
        "thresholds": threshold_df.to_dict(orient="records"),
    }
    with open(os.path.join(output_dir, "sl_atr_walk_forward_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # گزارش متنی
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("SL/ATR WALK-FORWARD VALIDATION REPORT")
    report_lines.append("=" * 70)
    report_lines.append(f"Number of walk-forward windows: {len(windows)}")
    report_lines.append(f"Baseline total PnL: {baseline_all['total_pnl']:.2f}")
    report_lines.append(f"Baseline expectancy: {baseline_all['expectancy']:.4f} R")
    report_lines.append(f"Baseline profit factor: {baseline_all['profit_factor']:.2f}")
    report_lines.append("-" * 70)

    for th in thresholds:
        stats = next((x for x in threshold_df.to_dict(orient='records') if x["threshold"] == th), None)
        if not stats:
            continue
        report_lines.append(f"\nThreshold SL/ATR <= {th}")
        report_lines.append(f"  Times selected: {stats['times_selected']} / {len(windows)}")
        report_lines.append(f"  Positive validation windows: {stats['positive_validation_windows']} / {stats['validation_windows_tested']}")
        report_lines.append(f"  Average validation expectancy: {stats['average_validation_expectancy']:.4f} R")
        report_lines.append(f"  Average validation PF: {stats['average_validation_pf']:.2f}")
        report_lines.append(f"  Total validation PnL: {stats['total_validation_pnl']:.2f}")
        report_lines.append(f"  Trade count min/avg/max: {stats['minimum_trade_count']}/{stats['average_trade_count']:.1f}/{stats['maximum_trade_count']}")

    # Robustness verdict heuristic
    report_lines.append("\n" + "-" * 70)
    report_lines.append("ROBUSTNESS VERDICT")
    report_lines.append("-" * 70)
    for th in thresholds:
        stats = next((x for x in threshold_df.to_dict(orient='records') if x["threshold"] == th), None)
        if not stats:
            continue
        if stats["positive_validation_rate"] > 0.6 and stats["average_validation_expectancy"] > 0:
            verdict = "STRONG ROBUST" if stats["average_validation_expectancy"] > 0.1 else "MODERATE ROBUST"
        elif stats["positive_validation_rate"] > 0.4:
            verdict = "WEAK"
        else:
            verdict = "UNSTABLE/REJECT"
        report_lines.append(f"SL/ATR <= {th}: {verdict}")

    report_lines.append("\n" + "=" * 70)
    report_lines.append("LIMITATIONS")
    report_lines.append("=" * 70)
    report_lines.append("Dataset contains only {} trades. Results are robustness evidence, not statistical proof.".format(total))
    report_lines.append("No live strategy modifications should be made based solely on this analysis.")

    report_text = "\n".join(report_lines)
    with open(os.path.join(output_dir, "sl_atr_walk_forward_report.txt"), "w") as f:
        f.write(report_text)

    return {
        "windows": windows,
        "threshold_stats": threshold_stats,
        "summary": summary,
        "baseline": baseline_all,
    }
