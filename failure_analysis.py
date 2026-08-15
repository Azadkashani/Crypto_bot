"""
ماژول تحلیل معاملات SL و TP برای ریشه‌یابی شکست‌ها.

فقط برای تحلیل آماری؛ هیچ‌گونه تغییری در استراتژی، ورود، خروج یا ریسک نمی‌دهد.
"""

from __future__ import annotations

import os
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import timezone, timedelta

import config
from indicators import (
    add_rsi,
    add_ema,
    add_adx,
    add_atr,
    add_volume_sma,
    detect_swings,
)
from choch import detect_choch
from bos import detect_bos


# ----------------------------------------------------------------------
# ثابت‌های تحلیل (فقط برای Analysis، نه Strategy)
# ----------------------------------------------------------------------
SL_ATR_TIGHT = 0.5
SL_ATR_WIDE = 3.0
VOLUME_RATIO_LOW = 0.5
VOLUME_RATIO_HIGH = 2.0
NEAR_SR_THRESHOLD = 0.005   # 0.5% فاصله تا Resistance/Support
ATR_VOL_HIGH = 1.5          # افزایش ناگهانی ATR نسبت به میانگین ۲۰ کندل قبل


class FailureAnalyzer:
    """
    تحلیل جامع معاملات SL و مقایسه با TP.
    """

    def __init__(self, provider, symbols: List[str]):
        self.provider = provider
        self.symbols = symbols
        self._precomputed: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # پیش‌محاسبه یک‌بار برای هر نماد
    # ------------------------------------------------------------------
    def _precompute_symbol(self, symbol: str) -> None:
        data = {}
        for tf in [config.TIMEFRAME_4H, config.TIMEFRAME_1H, config.TIMEFRAME_5M]:
            df = self.provider.get_ohlcv(symbol, tf, None, None)
            if df.empty:
                data[tf] = {"df": df}
                continue

            df = df.sort_index()
            enriched = df.copy()

            if tf == config.TIMEFRAME_5M:
                enriched = add_ema(enriched, period=config.EMA_FAST, src_col='close', col_name='ema_fast')
                enriched = add_ema(enriched, period=config.EMA_MID, src_col='close', col_name='ema_mid')
                enriched = add_ema(enriched, period=config.EMA_SLOW, src_col='close', col_name='ema_slow')
                enriched = add_rsi(enriched, period=config.RSI_PERIOD)
                enriched = add_atr(enriched, period=config.ATR_PERIOD)
                enriched = add_volume_sma(enriched, period=config.VOLUME_SMA_PERIOD)
                enriched = detect_swings(enriched)
                enriched = detect_choch(enriched)
                enriched = detect_bos(enriched)
                data[tf] = {"df": enriched}
            else:
                enriched = add_ema(enriched, period=config.EMA_FAST, src_col='close', col_name='ema_fast')
                enriched = add_ema(enriched, period=config.EMA_MID, src_col='close', col_name='ema_mid')
                enriched = add_ema(enriched, period=config.EMA_SLOW, src_col='close', col_name='ema_slow')
                enriched = add_adx(enriched, period=config.ADX_PERIOD)
                enriched = add_rsi(enriched, period=config.RSI_PERIOD)
                enriched = add_atr(enriched, period=config.ATR_PERIOD)
                data[tf] = {"df": enriched}

        self._precomputed[symbol] = data

    def _get_df(self, symbol: str, tf: str) -> pd.DataFrame:
        return self._precomputed.get(symbol, {}).get(tf, {}).get("df", pd.DataFrame())

    def _find_idx_for_time(self, symbol: str, tf: str, target_ts: pd.Timestamp) -> Optional[int]:
        df = self._get_df(symbol, tf)
        if df.empty:
            return None
        pos = df.index.searchsorted(pd.Timestamp(target_ts), side='right') - 1
        if pos < 0:
            return None
        return pos

    # ------------------------------------------------------------------
    # تحلیل یک معامله
    # ------------------------------------------------------------------
    def _analyze_single_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        symbol = trade.get("symbol")
        direction = trade.get("direction")
        entry_time = pd.Timestamp(trade.get("entry_time"))
        exit_time = pd.Timestamp(trade.get("exit_time"))
        entry_price = float(trade.get("entry_price"))
        sl = float(trade.get("stop_loss"))
        tp = float(trade.get("take_profit"))

        df5 = self._get_df(symbol, '5m')
        idx_entry = self._find_idx_for_time(symbol, '5m', entry_time)
        idx_exit = self._find_idx_for_time(symbol, '5m', exit_time)

        row = {
            "trade_id": trade.get("trade_id", None),
            "symbol": symbol,
            "direction": direction,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit": tp,
            "position_size": trade.get("position_size"),
            "risk_amount": trade.get("risk_amount"),
            "leverage": trade.get("leverage"),
            "exit_time": exit_time,
            "exit_reason": trade.get("exit_reason"),
            "pnl": trade.get("pnl"),
            "r_multiple": trade.get("r_multiple"),
            "regime_4h": trade.get("regime_4h"),
            "regime_1h": trade.get("regime_1h"),
        }

        if idx_entry is None:
            row.update({k: np.nan for k in [
                "rsi_entry", "rsi_min_3", "rsi_min_5", "rsi_min_10", "rsi_min_20",
                "atr_entry", "atr_ratio_20", "sl_distance_pct", "sl_atr_ratio",
                "volume_ratio", "distance_to_support", "distance_to_resistance",
                "choch_time", "candles_since_choch", "bos_time", "candles_since_bos",
                "mae_pct", "mae_atr", "mfe_pct", "mfe_atr",
                "post_sl_5", "post_sl_10", "post_sl_20", "post_sl_50",
                "time_to_exit_bars",
            ]})
            row["failure_reasons"] = ["UNKNOWN"] if trade.get("exit_reason") == "SL" else []
            row["failure_severity"] = 0.0
            return row

        # --- ویژگی‌های لحظه‌ی ورود (فقط داده‌های گذشته) ---
        rsi_series = df5[f"rsi_{config.RSI_PERIOD}"].to_numpy()
        atr_series = df5[f"atr_{config.ATR_PERIOD}"].to_numpy()
        volume = df5["volume"].to_numpy()
        volume_sma = df5[f"volume_sma_{config.VOLUME_SMA_PERIOD}"].to_numpy()
        close_arr = df5["close"].to_numpy()
        high_arr = df5["high"].to_numpy()
        low_arr = df5["low"].to_numpy()

        rsi_entry = rsi_series[idx_entry] if not np.isnan(rsi_series[idx_entry]) else np.nan
        atr_entry = atr_series[idx_entry] if not np.isnan(atr_series[idx_entry]) else np.nan

        # نسبت ATR به میانگین ۲۰ کندل قبل (برای تشخیص volatility expansion)
        if idx_entry >= 20:
            avg_atr_20 = np.nanmean(atr_series[idx_entry-20:idx_entry])
            atr_ratio_20 = atr_entry / avg_atr_20 if avg_atr_20 else np.nan
        else:
            atr_ratio_20 = np.nan

        # RSI min در بازه‌های گذشته
        def get_min_rsi(start, end):
            if start < 0:
                start = 0
            window = rsi_series[start:end]
            return np.nanmin(window) if len(window) else np.nan

        rsi_min_3 = get_min_rsi(idx_entry-2, idx_entry+1)
        rsi_min_5 = get_min_rsi(idx_entry-4, idx_entry+1)
        rsi_min_10 = get_min_rsi(idx_entry-9, idx_entry+1)
        rsi_min_20 = get_min_rsi(idx_entry-19, idx_entry+1)

        # فاصله تا SL
        if direction == "LONG":
            sl_dist_pct = (entry_price - sl) / entry_price
        else:
            sl_dist_pct = (sl - entry_price) / entry_price
        sl_atr_ratio = sl_dist_pct / (atr_entry / entry_price) if atr_entry else np.nan

        # حجم نسبی
        volume_ratio = volume[idx_entry] / volume_sma[idx_entry] if volume_sma[idx_entry] else np.nan

        # Support/Resistance از 50 کندل قبل (بدون Future)
        lookback = max(0, idx_entry-50)
        support = np.min(low_arr[lookback:idx_entry+1])
        resistance = np.max(high_arr[lookback:idx_entry+1])
        distance_to_support = (entry_price - support) / entry_price if support else np.nan
        distance_to_resistance = (resistance - entry_price) / entry_price if resistance else np.nan

        # CHOCH/BOS
        past = df5.iloc[:idx_entry+1]
        if direction == "LONG":
            choch_times = past.index[past["bullish_choch"]]
            bos_times = past.index[past["bullish_bos"]]
        else:
            choch_times = past.index[past["bearish_choch"]]
            bos_times = past.index[past["bearish_bos"]]

        if len(choch_times) > 0:
            last_choch = choch_times[-1]
            candles_since_choch = idx_entry - past.index.get_loc(last_choch)
        else:
            last_choch = None
            candles_since_choch = None

        if len(bos_times) > 0:
            last_bos = bos_times[-1]
            candles_since_bos = idx_entry - past.index.get_loc(last_bos)
        else:
            last_bos = None
            candles_since_bos = None

        # MAE / MFE از ورود تا خروج
        if idx_exit is not None and idx_exit >= idx_entry:
            exit_window = df5.iloc[idx_entry:idx_exit+1]
            if direction == "LONG":
                mae_price = exit_window["low"].min()
                mfe_price = exit_window["high"].max()
            else:
                mae_price = exit_window["high"].max()
                mfe_price = exit_window["low"].min()
            mae_pct = (entry_price - mae_price) / entry_price if direction == "LONG" else (mae_price - entry_price) / entry_price
            mfe_pct = (mfe_price - entry_price) / entry_price if direction == "LONG" else (entry_price - mfe_price) / entry_price
            mae_atr = mae_pct / (atr_entry / entry_price) if atr_entry else np.nan
            mfe_atr = mfe_pct / (atr_entry / entry_price) if atr_entry else np.nan
            time_to_exit_bars = idx_exit - idx_entry
        else:
            mae_pct = mfe_pct = mae_atr = mfe_atr = time_to_exit_bars = np.nan

        # تحلیل بعد از SL (فقط برای SL)
        post_sl_5 = post_sl_10 = post_sl_20 = post_sl_50 = np.nan
        if trade.get("exit_reason") == "SL" and idx_exit is not None and idx_exit < len(df5)-1:
            future = df5.iloc[idx_exit+1:]
            if direction == "LONG":
                if len(future) >= 5:
                    post_sl_5 = (future["high"].iloc[:5].max() - entry_price) / entry_price
                if len(future) >= 10:
                    post_sl_10 = (future["high"].iloc[:10].max() - entry_price) / entry_price
                if len(future) >= 20:
                    post_sl_20 = (future["high"].iloc[:20].max() - entry_price) / entry_price
                if len(future) >= 50:
                    post_sl_50 = (future["high"].iloc[:50].max() - entry_price) / entry_price
            else:
                if len(future) >= 5:
                    post_sl_5 = (entry_price - future["low"].iloc[:5].min()) / entry_price
                if len(future) >= 10:
                    post_sl_10 = (entry_price - future["low"].iloc[:10].min()) / entry_price
                if len(future) >= 20:
                    post_sl_20 = (entry_price - future["low"].iloc[:20].min()) / entry_price
                if len(future) >= 50:
                    post_sl_50 = (entry_price - future["low"].iloc[:50].min()) / entry_price

        row.update({
            "rsi_entry": rsi_entry,
            "rsi_min_3": rsi_min_3,
            "rsi_min_5": rsi_min_5,
            "rsi_min_10": rsi_min_10,
            "rsi_min_20": rsi_min_20,
            "atr_entry": atr_entry,
            "atr_ratio_20": atr_ratio_20,
            "sl_distance_pct": sl_dist_pct,
            "sl_atr_ratio": sl_atr_ratio,
            "volume_ratio": volume_ratio,
            "distance_to_support": distance_to_support,
            "distance_to_resistance": distance_to_resistance,
            "choch_time": last_choch,
            "candles_since_choch": candles_since_choch,
            "bos_time": last_bos,
            "candles_since_bos": candles_since_bos,
            "mae_pct": mae_pct,
            "mae_atr": mae_atr,
            "mfe_pct": mfe_pct,
            "mfe_atr": mfe_atr,
            "time_to_exit_bars": time_to_exit_bars,
            "post_sl_5": post_sl_5,
            "post_sl_10": post_sl_10,
            "post_sl_20": post_sl_20,
            "post_sl_50": post_sl_50,
        })

        # --- Failure Reasons فقط برای SL ---
        failure_reasons: List[str] = []
        if trade.get("exit_reason") == "SL":
            # تراز نبودن Higher Timeframe
            if direction == "LONG":
                if trade.get("regime_4h") != "BULLISH" or trade.get("regime_1h") != "BULLISH":
                    failure_reasons.append("HTF_NOT_ALIGNED")
            else:  # SHORT
                if trade.get("regime_4h") != "BEARISH" or trade.get("regime_1h") != "BEARISH":
                    failure_reasons.append("HTF_NOT_ALIGNED")

            # RSI
            if not np.isnan(rsi_entry):
                if direction == "LONG":
                    if rsi_entry < config.RSI_OVERSOLD:
                        failure_reasons.append("RSI_ENTRY_TOO_EARLY")
                    elif rsi_entry > 50:
                        failure_reasons.append("RSI_ENTRY_TOO_LATE")
                else:
                    if rsi_entry > config.RSI_OVERBOUGHT:
                        failure_reasons.append("RSI_ENTRY_TOO_EARLY")
                    elif rsi_entry < 50:
                        failure_reasons.append("RSI_ENTRY_TOO_LATE")

            # SL ATR
            if not np.isnan(sl_atr_ratio):
                if sl_atr_ratio < SL_ATR_TIGHT:
                    failure_reasons.append("SL_TOO_TIGHT")
                elif sl_atr_ratio > SL_ATR_WIDE:
                    failure_reasons.append("SL_TOO_WIDE")

            # Volatility
            if not np.isnan(atr_ratio_20):
                if atr_ratio_20 > ATR_VOL_HIGH:
                    failure_reasons.append("HIGH_VOLATILITY")
                elif atr_ratio_20 < 0.5:
                    failure_reasons.append("LOW_VOLATILITY")

            # Volume confirmation
            if not np.isnan(volume_ratio):
                if volume_ratio < VOLUME_RATIO_LOW:
                    failure_reasons.append("LOW_VOLUME_CONFIRMATION")

            # فاصله به Resistance/Support
            if not np.isnan(distance_to_resistance):
                if direction == "LONG" and distance_to_resistance < NEAR_SR_THRESHOLD:
                    failure_reasons.append("ENTRY_TOO_CLOSE_TO_RESISTANCE")
                if direction == "SHORT" and distance_to_support < NEAR_SR_THRESHOLD:
                    failure_reasons.append("ENTRY_TOO_CLOSE_TO_SUPPORT")

            # اگر بعد از SL بازار به نفع جهت قبلی حرکت کرده = Stop Hunt
            if post_sl_5 is not None and not np.isnan(post_sl_5):
                if post_sl_5 > sl_dist_pct:
                    failure_reasons.append("STOP_HUNT")

            if not failure_reasons:
                failure_reasons.append("UNKNOWN")

        row["failure_reasons"] = failure_reasons

        # شدت شکست (فقط برای SL)
        if trade.get("exit_reason") == "SL":
            severity = 0.0
            # تعداد دلایل
            severity += min(len(failure_reasons), 3) * 15
            # MAE بزرگ
            if not np.isnan(mae_atr):
                severity += min(mae_atr, 3.0) * 10
            # خروج سریع
            if not np.isnan(time_to_exit_bars) and time_to_exit_bars <= 3:
                severity += 15
            # مومنتوم مخالف (MFE/MAE)
            if not np.isnan(mfe_atr) and not np.isnan(mae_atr):
                if mfe_atr < 0.5 * mae_atr:
                    severity += 15
            # SL خیلی غیرعادی
            if not np.isnan(sl_atr_ratio) and sl_atr_ratio > 4:
                severity += 10
            row["failure_severity"] = min(severity, 100.0)
        else:
            row["failure_severity"] = 0.0

        return row

    def analyze(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """تحلیل کامل و ساخت گزارش‌ها."""
        # Precompute symbols
        for sym in self.symbols:
            if sym not in self._precomputed:
                self._precompute_symbol(sym)

        all_rows = []
        for t in trades:
            row = self._analyze_single_trade(t)
            all_rows.append(row)

        sl_rows = [r for r in all_rows if r["exit_reason"] == "SL"]
        tp_rows = [r for r in all_rows if r["exit_reason"] == "TP"]
        total_trades = len(all_rows)
        total_sl = len(sl_rows)
        total_tp = len(tp_rows)
        sl_rate = total_sl / total_trades if total_trades else 0.0

        # اعتبارسنجی Alignment
        misclassified = 0
        for r in sl_rows:
            dir_ = r["direction"]
            r4 = r["regime_4h"]
            r1 = r["regime_1h"]
            expected_align = (dir_ == "LONG" and r4 == "BULLISH" and r1 == "BULLISH") or \
                             (dir_ == "SHORT" and r4 == "BEARISH" and r1 == "BEARISH")
            if "HTF_NOT_ALIGNED" in r["failure_reasons"] and expected_align:
                misclassified += 1
        alignment_ok = misclassified == 0

        # جمع‌بندی دلایل
        reason_counts: Dict[str, int] = {}
        for r in sl_rows:
            for reason in r["failure_reasons"]:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        failure_summary = []
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            subset = [r for r in sl_rows if reason in r["failure_reasons"]]
            avg_loss = np.mean([r["pnl"] for r in subset]) if subset else 0.0
            avg_r = np.mean([r["r_multiple"] for r in subset]) if subset else 0.0
            avg_mae = np.nanmean([r["mae_pct"] for r in subset]) if subset else 0.0
            avg_mfe = np.nanmean([r["mfe_pct"] for r in subset]) if subset else 0.0
            avg_sl_atr = np.nanmean([r["sl_atr_ratio"] for r in subset]) if subset else 0.0
            failure_summary.append({
                "failure_reason": reason,
                "count": count,
                "percentage": (count / total_sl * 100) if total_sl else 0.0,
                "avg_loss": avg_loss,
                "average_r": avg_r,
                "avg_mae_pct": avg_mae,
                "avg_mfe_pct": avg_mfe,
                "avg_sl_atr_ratio": avg_sl_atr,
            })

        # مقایسه SL vs TP ویژگی‌ها
        feature_keys = [
            "rsi_entry", "atr_entry", "sl_atr_ratio", "volume_ratio",
            "distance_to_support", "distance_to_resistance", "mae_pct", "mfe_pct",
            "candles_since_choch", "candles_since_bos"
        ]
        comparison = []
        for key in feature_keys:
            sl_vals = pd.Series([r.get(key) for r in sl_rows], dtype=float).dropna()
            tp_vals = pd.Series([r.get(key) for r in tp_rows], dtype=float).dropna()
            comparison.append({
                "feature": key,
                "SL_mean": float(sl_vals.mean()) if not sl_vals.empty else np.nan,
                "SL_median": float(sl_vals.median()) if not sl_vals.empty else np.nan,
                "TP_mean": float(tp_vals.mean()) if not tp_vals.empty else np.nan,
                "TP_median": float(tp_vals.median()) if not tp_vals.empty else np.nan,
                "diff_mean": float(sl_vals.mean() - tp_vals.mean()) if not sl_vals.empty and not tp_vals.empty else np.nan,
            })

        # Bucket analysis بر اساس SL/ATR
        buckets = {
            "< 1 ATR": [],
            "1-2 ATR": [],
            "2-3 ATR": [],
            "3-4 ATR": [],
            "> 4 ATR": [],
        }
        for r in all_rows:
            val = r.get("sl_atr_ratio")
            if val is None or np.isnan(val):
                continue
            if val < 1:
                buckets["< 1 ATR"].append(r)
            elif val < 2:
                buckets["1-2 ATR"].append(r)
            elif val < 3:
                buckets["2-3 ATR"].append(r)
            elif val < 4:
                buckets["3-4 ATR"].append(r)
            else:
                buckets["> 4 ATR"].append(r)

        bucket_analysis = []
        for bucket, rows in buckets.items():
            if not rows:
                continue
            sl_count = sum(1 for r in rows if r["exit_reason"] == "SL")
            tp_count = sum(1 for r in rows if r["exit_reason"] == "TP")
            sl_rate_bucket = sl_count / len(rows) if rows else 0.0
            avg_pnl = np.mean([r["pnl"] for r in rows])
            avg_r = np.mean([r["r_multiple"] for r in rows])
            avg_mae = np.nanmean([r["mae_pct"] for r in rows])
            avg_mfe = np.nanmean([r["mfe_pct"] for r in rows])
            bucket_analysis.append({
                "sl_atr_bucket": bucket,
                "total_trades": len(rows),
                "SL_count": sl_count,
                "TP_count": tp_count,
                "SL_rate": sl_rate_bucket,
                "avg_pnl": avg_pnl,
                "avg_r": avg_r,
                "avg_mae_pct": avg_mae,
                "avg_mfe_pct": avg_mfe,
            })

        # ترکیب‌های دلایل
        combo_counts: Dict[str, int] = {}
        for r in sl_rows:
            reasons = r["failure_reasons"]
            combo = " + ".join(sorted(set(reasons)))
            combo_counts[combo] = combo_counts.get(combo, 0) + 1

        combo_analysis = []
        for combo, count in sorted(combo_counts.items(), key=lambda x: -x[1]):
            subset = [r for r in sl_rows if " + ".join(sorted(set(r["failure_reasons"]))) == combo]
            avg_loss = np.mean([r["pnl"] for r in subset])
            avg_mae = np.nanmean([r["mae_pct"] for r in subset])
            avg_mfe = np.nanmean([r["mfe_pct"] for r in subset])
            combo_analysis.append({
                "combination": combo,
                "count": count,
                "avg_loss": avg_loss,
                "avg_mae_pct": avg_mae,
                "avg_mfe_pct": avg_mfe,
            })

        return {
            "total_trades": total_trades,
            "total_sl": total_sl,
            "total_tp": total_tp,
            "sl_rate": sl_rate,
            "alignment_ok": alignment_ok,
            "failure_summary": failure_summary,
            "feature_comparison": comparison,
            "bucket_analysis": bucket_analysis,
            "combination_analysis": combo_analysis,
            "all_rows": all_rows,
            "sl_rows": sl_rows,
            "tp_rows": tp_rows,
        }

    def write_outputs(self, report: Dict[str, Any], output_dir: str = "analysis"):
        os.makedirs(output_dir, exist_ok=True)

        # SL Failure Analysis CSV
        sl_df = pd.DataFrame(report["sl_rows"])
        sl_csv = os.path.join(output_dir, "sl_failure_analysis.csv")
        sl_df.to_csv(sl_csv, index=False)

        # Failure Summary
        summary_df = pd.DataFrame(report["failure_summary"])
        summary_csv = os.path.join(output_dir, "failure_summary.csv")
        summary_df.to_csv(summary_csv, index=False)

        # Feature Comparison
        comp_df = pd.DataFrame(report["feature_comparison"])
        comp_csv = os.path.join(output_dir, "failure_feature_comparison.csv")
        comp_df.to_csv(comp_csv, index=False)

        # Combinations
        combo_df = pd.DataFrame(report["combination_analysis"])
        combo_csv = os.path.join(output_dir, "failure_combinations.csv")
        combo_df.to_csv(combo_csv, index=False)

        # Bucket Analysis
        bucket_df = pd.DataFrame(report["bucket_analysis"])
        bucket_csv = os.path.join(output_dir, "sl_bucket_analysis.csv")
        bucket_df.to_csv(bucket_csv, index=False)

        # JSON Report
        json_report = {k: v for k, v in report.items() if k not in ("all_rows", "sl_rows", "tp_rows")}
        json_path = os.path.join(output_dir, "failure_report.json")
        with open(json_path, "w") as f:
            json.dump(json_report, f, indent=2, default=str)

        return {
            "sl_csv": sl_csv,
            "summary_csv": summary_csv,
            "feature_comparison_csv": comp_csv,
            "combinations_csv": combo_csv,
            "bucket_csv": bucket_csv,
            "json_report": json_path,
        }

    def print_report(self, report: Dict[str, Any]):
        print("\n" + "=" * 70)
        print("SL FAILURE ANALYSIS V2")
        print("=" * 70)
        print("BACKTEST")
        print(f"Total Trades: {report['total_trades']}")
        print(f"SL Trades: {report['total_sl']}")
        print(f"TP Trades: {report['total_tp']}")
        print(f"SL Rate: {report['sl_rate']:.1%}")
        print("-" * 70)
        print("VALIDATION")
        print(f"HTF Alignment Consistency: {'PASS' if report['alignment_ok'] else 'FAIL'}")
        print("-" * 70)
        print("TOP FAILURE REASONS")
        for i, fs in enumerate(report["failure_summary"][:10], 1):
            print(f"{i}. {fs['failure_reason']}")
            print(f"   Count: {fs['count']} ({fs['percentage']:.1f}%) AvgLoss: {fs['avg_loss']:.2f} AvgR: {fs['average_r']:.2f} AvgMAE: {fs['avg_mae_pct']:.4f} AvgMFE: {fs['avg_mfe_pct']:.4f} AvgSL/ATR: {fs['avg_sl_atr_ratio']:.2f}")
        print("-" * 70)
        print("SL vs TP FEATURE COMPARISON")
        print(f"{'Feature':<30}{'SL Mean':>12}{'TP Mean':>12}{'Diff':>10}")
        for comp in report["feature_comparison"]:
            print(f"{comp['feature']:<30}{comp['SL_mean']:>12.4f}{comp['TP_mean']:>12.4f}{comp['diff_mean']:>10.4f}")
        print("-" * 70)
        print("SL/ATR BUCKET ANALYSIS")
        print(f"{'Bucket':<15}{'Total':>6}{'SL':>4}{'TP':>4}{'SLRate':>10}{'AvgPnl':>10}{'AvgR':>10}")
        for b in report["bucket_analysis"]:
            print(f"{b['sl_atr_bucket']:<15}{b['total_trades']:>6}{b['SL_count']:>4}{b['TP_count']:>4}{b['SL_rate']:>10.1%}{b['avg_pnl']:>10.2f}{b['avg_r']:>10.2f}")
        print("-" * 70)
        print("FAILURE COMBINATIONS")
        for c in report["combination_analysis"][:10]:
            print(f"{c['combination']:<50} Count: {c['count']} AvgLoss: {c['avg_loss']:.2f} AvgMAE: {c['avg_mae_pct']:.4f} AvgMFE: {c['avg_mfe_pct']:.4f}")
        print("=" * 70)
