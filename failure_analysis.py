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
        """آخرین ایندکس کندل بسته‌شده‌ی <= target_ts."""
        df = self._get_df(symbol, tf)
        if df.empty:
            return None
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
            row.update({
                "rsi_entry": None,
                "rsi_min_3": None,
                "rsi_min_5": None,
                "rsi_min_10": None,
                "rsi_min_20": None,
                "atr_entry": None,
                "sl_distance_pct": None,
                "sl_atr_ratio": None,
                "volume_ratio": None,
                "distance_to_support": None,
                "distance_to_resistance": None,
                "choch_time": None,
                "candles_since_choch": None,
                "bos_time": None,
                "candles_since_bos": None,
                "mae_pct": None,
                "mae_atr": None,
                "mfe_pct": None,
                "mfe_atr": None,
                "post_sl_5": None,
                "post_sl_10": None,
                "post_sl_20": None,
                "post_sl_50": None,
                "failure_reasons": ["UNKNOWN"],
            })
            return row

        rsi_entry = df5[f"rsi_{config.RSI_PERIOD}"].iloc[idx_entry]
        atr_entry = df5[f"atr_{config.ATR_PERIOD}"].iloc[idx_entry]
        volume_entry = df5["volume"].iloc[idx_entry]
        volume_sma_entry = df5[f"volume_sma_{config.VOLUME_SMA_PERIOD}"].iloc[idx_entry]
        close_entry = df5["close"].iloc[idx_entry]

        def safe_min(arr, start, end):
            if end < start or start < 0:
                return np.nan
            return arr[start:end].min()

        rsi_arr = df5[f"rsi_{config.RSI_PERIOD}"].to_numpy()
        rsi_min_3 = safe_min(rsi_arr, max(0, idx_entry-2), idx_entry+1)
        rsi_min_5 = safe_min(rsi_arr, max(0, idx_entry-4), idx_entry+1)
        rsi_min_10 = safe_min(rsi_arr, max(0, idx_entry-9), idx_entry+1)
        rsi_min_20 = safe_min(rsi_arr, max(0, idx_entry-19), idx_entry+1)

        if direction == "LONG":
            sl_dist_pct = (entry_price - sl) / entry_price
        else:
            sl_dist_pct = (sl - entry_price) / entry_price
        sl_atr_ratio = sl_dist_pct / (atr_entry / entry_price) if atr_entry else np.nan

        volume_ratio = volume_entry / volume_sma_entry if volume_sma_entry else np.nan

        # Support/Resistance
        lookback = max(0, idx_entry-50)
        window = df5.iloc[lookback:idx_entry+1]
        support = window["low"].min()
        resistance = window["high"].max()
        distance_to_support = (entry_price - support) / entry_price if support else np.nan
        distance_to_resistance = (resistance - entry_price) / entry_price if resistance else np.nan

        # CHOCH/BOS
        bullish_choch = df5["bullish_choch"].iloc[:idx_entry+1]
        bearish_choch = df5["bearish_choch"].iloc[:idx_entry+1]
        bullish_bos = df5["bullish_bos"].iloc[:idx_entry+1]
        bearish_bos = df5["bearish_bos"].iloc[:idx_entry+1]

        if direction == "LONG":
            if bullish_choch.any():
                last_choch = df5.index[bullish_choch[bullish_choch].index][-1]
                candles_since_choch = idx_entry - df5.index.get_loc(last_choch)
            else:
                last_choch = None
                candles_since_choch = None
            if bullish_bos.any():
                last_bos = df5.index[bullish_bos[bullish_bos].index][-1]
                candles_since_bos = idx_entry - df5.index.get_loc(last_bos)
            else:
                last_bos = None
                candles_since_bos = None
        else:
            if bearish_choch.any():
                last_choch = df5.index[bearish_choch[bearish_choch].index][-1]
                candles_since_choch = idx_entry - df5.index.get_loc(last_choch)
            else:
                last_choch = None
                candles_since_choch = None
            if bearish_bos.any():
                last_bos = df5.index[bearish_bos[bearish_bos].index][-1]
                candles_since_bos = idx_entry - df5.index.get_loc(last_bos)
            else:
                last_bos = None
                candles_since_bos = None

        # MAE / MFE
        if idx_exit is not None and idx_exit >= idx_entry:
            window2 = df5.iloc[idx_entry:idx_exit+1]
            if direction == "LONG":
                mae_price = window2["low"].min()
                mfe_price = window2["high"].max()
            else:
                mae_price = window2["high"].max()
                mfe_price = window2["low"].min()
            mae_pct = (entry_price - mae_price) / entry_price if direction == "LONG" else (mae_price - entry_price) / entry_price
            mfe_pct = (mfe_price - entry_price) / entry_price if direction == "LONG" else (entry_price - mfe_price) / entry_price
            mae_atr = mae_pct / (atr_entry / entry_price) if atr_entry else np.nan
            mfe_atr = mfe_pct / (atr_entry / entry_price) if atr_entry else np.nan
        else:
            mae_pct = mfe_pct = mae_atr = mfe_atr = np.nan

        # Post-SL Analysis
        post_sl_5 = post_sl_10 = post_sl_20 = post_sl_50 = np.nan
        if idx_exit is not None and idx_exit < len(df5) - 1:
            future = df5.iloc[idx_exit+1:]
            if direction == "LONG":
                post_sl_5 = (future["high"].iloc[:5].max() - entry_price) / entry_price if len(future) >= 5 else np.nan
                post_sl_10 = (future["high"].iloc[:10].max() - entry_price) / entry_price if len(future) >= 10 else np.nan
                post_sl_20 = (future["high"].iloc[:20].max() - entry_price) / entry_price if len(future) >= 20 else np.nan
                post_sl_50 = (future["high"].iloc[:50].max() - entry_price) / entry_price if len(future) >= 50 else np.nan
            else:
                post_sl_5 = (entry_price - future["low"].iloc[:5].min()) / entry_price if len(future) >= 5 else np.nan
                post_sl_10 = (entry_price - future["low"].iloc[:10].min()) / entry_price if len(future) >= 10 else np.nan
                post_sl_20 = (entry_price - future["low"].iloc[:20].min()) / entry_price if len(future) >= 20 else np.nan
                post_sl_50 = (entry_price - future["low"].iloc[:50].min()) / entry_price if len(future) >= 50 else np.nan

        # Failure reasons
        reasons = []
        if trade.get("regime_4h") != direction or trade.get("regime_1h") != direction:
            reasons.append("HTF_NOT_ALIGNED")
        if not np.isnan(rsi_entry):
            if direction == "LONG":
                if rsi_entry < 30:
                    reasons.append("RSI_ENTRY_TOO_EARLY")
                elif rsi_entry > 50:
                    reasons.append("RSI_ENTRY_TOO_LATE")
            else:
                if rsi_entry > 70:
                    reasons.append("RSI_ENTRY_TOO_EARLY")
                elif rsi_entry < 50:
                    reasons.append("RSI_ENTRY_TOO_LATE")
        if not np.isnan(sl_atr_ratio):
            if sl_atr_ratio < 0.5:
                reasons.append("SL_TOO_TIGHT")
            elif sl_atr_ratio > 2.0:
                reasons.append("SL_TOO_WIDE")
        if not np.isnan(volume_ratio):
            if volume_ratio < 0.5:
                reasons.append("LOW_VOLUME_CONFIRMATION")
            elif volume_ratio > 2.0:
                reasons.append("HIGH_VOLATILITY")
        if not np.isnan(distance_to_resistance):
            if direction == "LONG" and distance_to_resistance < 0.01:
                reasons.append("ENTRY_TOO_CLOSE_TO_RESISTANCE")
            if direction == "SHORT" and distance_to_support < 0.01:
                reasons.append("ENTRY_TOO_CLOSE_TO_SUPPORT")
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
        # precompute for all symbols
        for sym in self.symbols:
            if sym not in self._precomputed:
                self._precompute_symbol(sym)

        sl_rows = []
        for t in trades:
            if t.get("exit_reason") == "SL":
                row = self._analyze_single_sl(t)
                sl_rows.append(row)

        total_sl = len(sl_rows)
        total_tp = sum(1 for t in trades if t.get("exit_reason") == "TP")
        total_trades = len(trades)
        sl_rate = total_sl / total_trades if total_trades else 0.0

        reason_counts: Dict[str, int] = {}
        for row in sl_rows:
            for r in row["failure_reasons"]:
                reason_counts[r] = reason_counts.get(r, 0) + 1

        failure_summary = []
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
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
