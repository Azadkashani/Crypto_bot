"""
ماژول تحلیل معاملات SL (Stop Loss) و تولید گزارش Failure Analysis.

این ماژول صرفاً تحلیلی است و هیچ تغییری در استراتژی، ورود، خروج
یا مدیریت ریسک ایجاد نمی‌کند. از داده‌های تاریخی و trade های موجود
برای تحلیل عمیق شکست‌ها استفاده می‌شود.
"""

from __future__ import annotations

import os
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import timezone, timedelta

import config
from indicators import add_rsi, add_ema, add_adx, add_volume_sma, detect_swings
from choch import detect_choch
from bos import detect_bos


class FailureAnalyzer:
    """
    تحلیل معاملات SL و تولید گزارش‌های آماری.
    """

    def __init__(self, provider, symbols: List[str]):
        self.provider = provider
        self.symbols = symbols
        self._precomputed: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # بارگذاری و پیش‌محاسبه داده‌ها
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

            # 5m پیش‌محاسبات کامل
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
                # برای 1h و 4h فقط EMA و ADX و RSI و ATR
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
        """آخرین ایندکس کندل بسته‌شده‌ی <= target_ts."""
        df = self._get_df(symbol, tf)
        if df.empty:
            return None
        # فرض می‌کنیم کندل‌ها بسته شده‌اند و ایندکس زمان شروع است.
        # برای مطابقت با decision_time که زمان بسته شدن است، باید کندلی که start + delta <= target_ts را پیدا کنیم.
        # ساده‌سازی: مقایسه مستقیم ایندکس <= target_ts.
        pos = df.index.searchsorted(pd.Timestamp(target_ts), side='right') - 1
        if pos < 0:
            return None
        return pos

    # ------------------------------------------------------------------
    # محاسبات تحلیلی برای یک معامله
    # ------------------------------------------------------------------
    def _analyze_single_sl(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        symbol = trade.get("symbol")
        direction = trade.get("direction")
        entry_time = pd.Timestamp(trade.get("entry_time"))
        exit_time = pd.Timestamp(trade.get("exit_time"))
        entry_price = float(trade.get("entry_price"))
        sl = float(trade.get("stop_loss"))
        tp = float(trade.get("take_profit"))

        # داده 5m
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
            row.update({k: None for k in [
                "rsi_entry", "rsi_min_3", "rsi_min_5", "rsi_min_10", "rsi_min_20",
                "atr_entry", "sl_distance_pct", "sl_atr_ratio",
                "volume_ratio", "distance_to_support", "distance_to_resistance",
                "choch_time", "candles_since_choch", "bos_time", "candles_since_bos",
                "mae_pct", "mae_atr", "mfe_pct", "mfe_atr",
                "post_sl_5", "post_sl_10", "post_sl_20", "post_sl_50",
            ]})
            row["failure_reasons"] = ["UNKNOWN"]
            return row

        # مقادیر در لحظه ورود
        rsi_entry = df5[f"rsi_{config.RSI_PERIOD}"].iloc[idx_entry]
        atr_entry = df5[f"atr_{config.ATR_PERIOD}"].iloc[idx_entry]
        volume_entry = df5["volume"].iloc[idx_entry]
        volume_sma_entry = df5[f"volume_sma_{config.VOLUME_SMA_PERIOD}"].iloc[idx_entry]
        close_entry = df5["close"].iloc[idx_entry]

        # RSI min در بازه‌های قبلی
        if idx_entry >= 2:
            rsi_min_3 = df5[f"rsi_{config.RSI_PERIOD}"].iloc[max(0, idx_entry-2):idx_entry+1].min()
        else:
            rsi_min_3 = np.nan
        if idx_entry >= 4:
            rsi_min_5 = df5[f"rsi_{config.RSI_PERIOD}"].iloc[max(0, idx_entry-4):idx_entry+1].min()
        else:
            rsi_min_5 = np.nan
        if idx_entry >= 9:
            rsi_min_10 = df5[f"rsi_{config.RSI_PERIOD}"].iloc[max(0, idx_entry-9):idx_entry+1].min()
        else:
            rsi_min_10 = np.nan
        if idx_entry >= 19:
            rsi_min_20 = df5[f"rsi_{config.RSI_PERIOD}"].iloc[max(0, idx_entry-19):idx_entry+1].min()
        else:
            rsi_min_20 = np.nan

        # SL distance
        if direction == "LONG":
            sl_dist_pct = (entry_price - sl) / entry_price
        else:
            sl_dist_pct = (sl - entry_price) / entry_price
        sl_atr_ratio = sl_dist_pct / (atr_entry / entry_price) if atr_entry else np.nan

        # Volume ratio
        volume_ratio = volume_entry / volume_sma_entry if volume_sma_entry else np.nan

        # Support/Resistance از Swing ها
        swing_high = df5["swing_high"].iloc[max(0, idx_entry-50):idx_entry+1]
        swing_low = df5["swing_low"].iloc[max(0, idx_entry-50):idx_entry+1]
        support = df5["low"].iloc[max(0, idx_entry-50):idx_entry+1].min()
        resistance = df5["high"].iloc[max(0, idx_entry-50):idx_entry+1].max()
        distance_to_support = (entry_price - support) / entry_price if support else np.nan
        distance_to_resistance = (resistance - entry_price) / entry_price if resistance else np.nan

        # CHOCH/BOS timestamps and candles since
        bullish_choch = df5["bullish_choch"].iloc[:idx_entry+1]
        bearish_choch = df5["bearish_choch"].iloc[:idx_entry+1]
        bullish_bos = df5["bullish_bos"].iloc[:idx_entry+1]
        bearish_bos = df5["bearish_bos"].iloc[:idx_entry+1]

        if direction == "LONG":
            last_choch = df5.index[bullish_choch[bullish_choch].index] if bullish_choch.any() else None
            last_bos = df5.index[bullish_bos[bullish_bos].index] if bullish_bos.any() else None
        else:
            last_choch = df5.index[bearish_choch[bearish_choch].index] if bearish_choch.any() else None
            last_bos = df5.index[bearish_bos[bearish_bos].index] if bearish_bos.any() else None

        candles_since_choch = idx_entry - df5.index.get_loc(last_choch) if last_choch is not None else None
        candles_since_bos = idx_entry - df5.index.get_loc(last_bos) if last_bos is not None else None

        # MAE / MFE بین entry و exit
        if idx_exit is not None and idx_exit >= idx_entry:
            window = df5.iloc[idx_entry:idx_exit+1]
            if direction == "LONG":
                mae_price = window["low"].min()
                mfe_price = window["high"].max()
            else:
                mae_price = window["high"].max()
                mfe_price = window["low"].min()
            mae_pct = (entry_price - mae_price) / entry_price if direction == "LONG" else (mae_price - entry_price) / entry_price
            mfe_pct = (mfe_price - entry_price) / entry_price if direction == "LONG" else (entry_price - mfe_price) / entry_price
            mae_atr = mae_pct / (atr_entry / entry_price) if atr_entry else np.nan
            mfe_atr = mfe_pct / (atr_entry / entry_price) if atr_entry else np.nan
        else:
            mae_price = mfe_price = mae_pct = mfe_pct = mae_atr = mfe_atr = np.nan

        # حرکت بعد از SL (فقط برای تحلیل post-SL)
        post_sl_5 = post_sl_10 = post_sl_20 = post_sl_50 = np.nan
        if idx_exit is not None and idx_exit < len(df5) - 1:
            for horizon, col in [(5, "post_sl_5"), (10, "post_sl_10"), (20, "post_sl_20"), (50, "post_sl_50")]:
                end = min(idx_exit + 1 + horizon, len(df5))
                if end > idx_exit + 1:
                    future = df5.iloc[idx_exit+1:end]
                    if direction == "LONG":
                        max_fav = future["high"].max() - entry_price
                        max_adv = entry_price - future["low"].min()
                        post_move = max(max_fav, 0) / entry_price if max_fav > 0 else -max_adv / entry_price
                    else:
                        max_fav = entry_price - future["low"].min()
                        max_adv = future["high"].max() - entry_price
                        post_move = max(max_fav, 0) / entry_price if max_fav > 0 else -max_adv / entry_price
                    row[col] = post_move
                else:
                    row[col] = np.nan

        # Failure reasons
        reasons = []
        # HTF alignment
        if trade.get("regime_4h") != trade.get("direction") and trade.get("regime_1h") != trade.get("direction"):
            reasons.append("HTF_NOT_ALIGNED")
        # RSI too late/early
        if not np.isnan(rsi_entry):
            if direction == "LONG":
                if rsi_entry < 30: reasons.append("RSI_ENTRY_TOO_EARLY")
                elif rsi_entry > 50: reasons.append("RSI_ENTRY_TOO_LATE")
            else:
                if rsi_entry > 70: reasons.append("RSI_ENTRY_TOO_EARLY")
                elif rsi_entry < 50: reasons.append("RSI_ENTRY_TOO_LATE")
        # SL too tight
        if not np.isnan(sl_atr_ratio):
            if sl_atr_ratio < 0.5: reasons.append("SL_TOO_TIGHT")
            elif sl_atr_ratio > 2.0: reasons.append("SL_TOO_WIDE")
        # Volume ratio
        if not np.isnan(volume_ratio):
            if volume_ratio < 0.5: reasons.append("LOW_VOLUME_CONFIRMATION")
            elif volume_ratio > 2.0: reasons.append("HIGH_VOLATILITY")
        # Entry near resistance/support
        if not np.isnan(distance_to_resistance):
            if direction == "LONG" and distance_to_resistance < 0.01: reasons.append("ENTRY_TOO_CLOSE_TO_RESISTANCE")
            if direction == "SHORT" and distance_to_support < 0.01: reasons.append("ENTRY_TOO_CLOSE_TO_SUPPORT")
        # If no reasons
        if not reasons:
            reasons.append("UNKNOWN")

        row.update({
            "rsi_entry": rsi_entry,
            "rsi_min_3": rsi_min_3,
            "rsi_min_5": rsi_min_5,
            "rsi_min_10": rsi_min_10,
            "rsi_min_20": rsi_min_20,
            "atr_entry": atr_entry,
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
            "post_sl_5": post_sl_5,
            "post_sl_10": post_sl_10,
            "post_sl_20": post_sl_20,
            "post_sl_50": post_sl_50,
            "failure_reasons": reasons,
        })

        return row

    def analyze(self, trades: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        تحلیل همه معاملات SL و تولید خلاصه.
        """
        # اطمینان از precompute همه نمادها
        for sym in self.symbols:
            if sym not in self._precomputed:
                self._precompute_symbol(sym)

        sl_rows = []
        for t in trades:
            if t.get("exit_reason") == "SL":
                row = self._analyze_single_sl(t)
                sl_rows.append(row)

        # ساخت summary
        total_sl = len(sl_rows)
        total_tp = sum(1 for t in trades if t.get("exit_reason") == "TP")
        total_trades = len(trades)
        sl_rate = total_sl / total_trades if total_trades else 0.0

        # تجمیع failure reasons
        reason_counts: Dict[str, int] = {}
        for row in sl_rows:
            for r in row["failure_reasons"]:
                reason_counts[r] = reason_counts.get(r, 0) + 1

        failure_summary = []
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            # میانگین‌ها
            subset = [row for row in sl_rows if reason in row["failure_reasons"]]
            avg_loss = np.mean([row["pnl"] for row in subset]) if subset else 0.0
            avg_mae = np.nanmean([row["mae_pct"] for row in subset]) if subset else 0.0
            avg_mfe = np.nanmean([row["mfe_pct"] for row in subset]) if subset else 0.0
            avg_sl_atr = np.nanmean([row["sl_atr_ratio"] for row in subset]) if subset else 0.0
            failure_summary.append({
                "failure_reason": reason,
                "count": count,
                "percentage": (count / total_sl * 100) if total_sl else 0.0,
                "avg_loss": avg_loss,
                "avg_mae": avg_mae,
                "avg_mfe": avg_mfe,
                "avg_sl_atr_ratio": avg_sl_atr,
            })

        return sl_rows, {
            "total_trades": total_trades,
            "total_sl": total_sl,
            "total_tp": total_tp,
            "sl_rate": sl_rate,
            "failure_summary": failure_summary,
        }

    def write_csvs(self, sl_rows: List[Dict[str, Any]], summary: Dict[str, Any], output_dir: str = "analysis"):
        os.makedirs(output_dir, exist_ok=True)

        sl_df = pd.DataFrame(sl_rows)
        sl_csv = os.path.join(output_dir, "sl_failure_analysis.csv")
        sl_df.to_csv(sl_csv, index=False)

        summary_df = pd.DataFrame(summary["failure_summary"])
        summary_csv = os.path.join(output_dir, "failure_summary.csv")
        summary_df.to_csv(summary_csv, index=False)

        return sl_csv, summary_csv

    def print_report(self, summary: Dict[str, Any]):
        print("\n" + "=" * 70)
        print("SL FAILURE ANALYSIS")
        print("=" * 70)
        print(f"Total Trades: {summary['total_trades']}")
        print(f"SL Trades: {summary['total_sl']}")
        print(f"TP Trades: {summary['total_tp']}")
        print(f"SL Rate: {summary['sl_rate']:.1%}")
        print("-" * 70)
        print("TOP FAILURE REASONS")
        print("-" * 70)
        for i, fs in enumerate(summary["failure_summary"][:10], 1):
            print(f"{i}. {fs['failure_reason']}")
            print(f"   Count: {fs['count']}  Share: {fs['percentage']:.1f}%  Avg Loss: {fs['avg_loss']:.2f}  Avg MAE: {fs['avg_mae']:.4f}  Avg MFE: {fs['avg_mfe']:.4f}  Avg SL/ATR: {fs['avg_sl_atr_ratio']:.2f}")
        print("=" * 70)
