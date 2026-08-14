"""
Real Market Historical Backtest با پشتیبانی چند پوزیشن همزمان و بهینه‌سازی سرعت.

این نسخه داده‌ها را یک بار بارگذاری و ایندکس‌ها را پیش‌محاسبه می‌کند تا
در حلقه اصلی هیچ I/O یا slicing تکراری انجام نشود.

منطق Strategy / Scoring / Ranking / Risk / Position Sizing تغییر نکرده است.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timezone

import config
import strategy
import signal_scoring
from metrics import calculate_metrics

MIN_24H_VOLUME_USDT = getattr(config, "MIN_24H_VOLUME_USDT", 1_000_000)

def _timeframe_to_timedelta(tf: str) -> pd.Timedelta:
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == "m":
        return pd.Timedelta(minutes=value)
    if unit == "h":
        return pd.Timedelta(hours=value)
    if unit == "d":
        return pd.Timedelta(days=value)
    raise ValueError(f"Unsupported timeframe: {tf}")


def validate_ohlcv(df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    issues = []
    if df.empty:
        issues.append("empty")
    else:
        if not df.index.is_monotonic_increasing:
            issues.append("unsorted timestamps")
        if df.index.duplicated().any():
            issues.append("duplicate timestamps")
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                issues.append(f"missing column {col}")
            elif df[col].isnull().any():
                issues.append(f"NaN in {col}")
        if "high" in df.columns and "low" in df.columns and "close" in df.columns and "open" in df.columns:
            if (df["high"] < df[["open", "close"]].max(axis=1)).any():
                issues.append("high < max")
            if (df["low"] > df[["open", "close"]].min(axis=1)).any():
                issues.append("low > min")
        if "volume" in df.columns and (df["volume"] < 0).any():
            issues.append("negative volume")
    return {"valid": len(issues) == 0, "issues": issues}


class HistoricalDataProvider:
    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        raise NotImplementedError

    def get_volume_24h_usdt(self, symbol, timestamp):
        raise NotImplementedError


class HistoricalBacktestRunner:
    """
    اجرای Backtest چندنمادی با حداکثر 4 پوزیشن همزمان.
    """

    def __init__(
        self,
        provider: HistoricalDataProvider,
        symbols: List[str],
        initial_balance: Optional[float] = None,
        fee_rate: float = 0.0,
        slippage_rate: float = 0.0,
        max_positions: Optional[int] = None,
    ):
        self.provider = provider
        self.symbols = symbols
        self.initial_balance = initial_balance or config.ACCOUNT_BALANCE
        self.current_balance = float(self.initial_balance)
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions or config.MAX_CONCURRENT_POSITIONS
        self.trades: List[Dict[str, Any]] = []
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.candidates_count = 0
        self.selected_count = 0
        self.safety_rejections = 0
        self.equity_curve: List[Dict[str, Any]] = [
            {"timestamp": None, "balance": self.current_balance}
        ]

        # حافظه برای داده‌های پیش‌بارگذاری‌شده
        self._data_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
        self._closed_slice_cache: Dict[Tuple[str, str, pd.Timestamp], pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # بارگذاری یک‌بار داده و ساخت حافظه
    # ------------------------------------------------------------------
    def _load_all_data(self, start_date=None, end_date=None) -> None:
        """بارگذاری کامل همه DataFrameها یک بار و ذخیره در self._data_cache."""
        for symbol in self.symbols:
            for tf in [config.TIMEFRAME_4H, config.TIMEFRAME_1H, config.TIMEFRAME_5M]:
                df = self.provider.get_ohlcv(symbol, tf, start_date, end_date)
                if not df.empty:
                    df = df.sort_index()
                self._data_cache[(symbol, tf)] = df

    def _get_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """بازگرداندن DataFrame از حافظه."""
        return self._data_cache.get((symbol, timeframe), pd.DataFrame())

    def _get_closed_slice_cached(
        self,
        symbol: str,
        timeframe: str,
        decision_time: pd.Timestamp,
    ) -> pd.DataFrame:
        """
        دریافت برش بسته‌شده تا decision_time با استفاده از حافظه.

        این تابع از کش استفاده می‌کند و داده را دوباره slice نمی‌کند.
        """
        key = (symbol, timeframe, decision_time)
        if key in self._closed_slice_cache:
            return self._closed_slice_cache[key]

        df = self._get_data(symbol, timeframe)
        if df.empty:
            result = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        else:
            delta = _timeframe_to_timedelta(timeframe)
            # فقط کندل‌هایی که end_time <= decision_time
            mask = df.index + delta <= decision_time
            result = df.loc[mask]

        self._closed_slice_cache[key] = result
        return result

    def _get_all_decision_times(self) -> List[pd.Timestamp]:
        """ترکیب زمان‌های بسته‌شدن کندل‌های 5m همه Symbolها."""
        times = set()
        for symbol in self.symbols:
            df = self._get_data(symbol, config.TIMEFRAME_5M)
            if df.empty:
                continue
            delta = _timeframe_to_timedelta(config.TIMEFRAME_5M)
            times.update(df.index + delta)
        return sorted(times)

    # ------------------------------------------------------------------
    # اجرای Backtest
    # ------------------------------------------------------------------
    def run(self, start_date=None, end_date=None):
        # بارگذاری یک‌بار داده
        self._load_all_data(start_date, end_date)

        data_quality_report = {}
        for symbol in self.symbols:
            for tf in [config.TIMEFRAME_4H, config.TIMEFRAME_1H, config.TIMEFRAME_5M]:
                df = self._get_data(symbol, tf)
                data_quality_report[f"{symbol}:{tf}"] = validate_ohlcv(df, tf)

        decision_times = self._get_all_decision_times()

        for decision_time in decision_times:
            if start_date is not None and decision_time < start_date:
                continue
            if end_date is not None and decision_time > end_date:
                continue

            # مدیریت خروج پوزیشن‌های باز
            for sym in list(self.open_positions.keys()):
                closed = self._try_exit_cached(self.open_positions[sym], decision_time)
                if closed:
                    del self.open_positions[sym]

            if len(self.open_positions) >= self.max_positions:
                continue

            candidates = []
            for symbol in self.symbols:
                if symbol in self.open_positions:
                    continue

                # حجم 24 ساعته از Provider (در Backtest واقعی از پیش‌فرض یا تاریخچه)
                volume = self.provider.get_volume_24h_usdt(symbol, decision_time)
                if volume is None or volume < MIN_24H_VOLUME_USDT:
                    continue

                df_4h = self._get_closed_slice_cached(symbol, config.TIMEFRAME_4H, decision_time)
                df_1h = self._get_closed_slice_cached(symbol, config.TIMEFRAME_1H, decision_time)
                df_5m = self._get_closed_slice_cached(symbol, config.TIMEFRAME_5M, decision_time)

                if df_5m.empty:
                    continue

                signal = strategy.generate_signal(
                    df_4h,
                    df_1h,
                    df_5m,
                    as_of=decision_time,
                    account_balance=self.current_balance,
                    symbol=symbol,
                )

                if signal.get("valid") is not True or signal.get("signal") not in ("LONG", "SHORT"):
                    continue

                candidate = {**signal, "symbol": symbol, "volume_24h_usdt": volume}
                score = signal_scoring.calculate_score(candidate)
                if score is None:
                    continue
                candidate["score"] = score
                candidates.append(candidate)

            if not candidates:
                continue

            self.candidates_count += len(candidates)

            # فقط بهترین کاندید برای هر نماد
            best_per_symbol = {}
            for cand in candidates:
                sym = cand["symbol"]
                if sym not in best_per_symbol or cand["score"] > best_per_symbol[sym]["score"]:
                    best_per_symbol[sym] = cand
            candidates = list(best_per_symbol.values())

            ranked = signal_scoring.rank_signals(candidates)
            slots = self.max_positions - len(self.open_positions)
            selected = ranked[:slots]
            self.selected_count += len(selected)

            for best in selected:
                ok, reason = self._safety_check_cached(best, decision_time)
                if not ok:
                    self.safety_rejections += 1
                    continue

                entry = best.get("entry_price")
                sl = best.get("stop_loss")
                tp = best.get("take_profit")
                size = best.get("position_size")
                risk = best.get("risk_amount")

                if best["signal"] == "LONG":
                    fill_price = entry * (1 + self.slippage_rate)
                else:
                    fill_price = entry * (1 - self.slippage_rate)

                self.open_positions[best["symbol"]] = {
                    "symbol": best["symbol"],
                    "direction": best["signal"],
                    "entry_time": decision_time,
                    "entry_price": float(fill_price),
                    "stop_loss": float(sl),
                    "take_profit": float(tp),
                    "position_size": float(size),
                    "risk_amount": float(risk),
                    "score": best.get("score"),
                    "regime_4h": best.get("regime_4h"),
                    "regime_1h": best.get("regime_1h"),
                }

        # بستن پوزیشن‌های باز باقی‌مانده
        for sym in list(self.open_positions.keys()):
            self._close_at_end_cached(self.open_positions[sym], end_date)
            del self.open_positions[sym]

        # ساخت equity curve
        equity_times = []
        balances = []
        for trade in self.trades:
            equity_times.append(trade["exit_time"])
            balances.append(trade["balance_after"])
        if equity_times:
            self.equity_curve = [{"timestamp": t, "balance": b} for t, b in zip(equity_times, balances)]

        metrics = self._compute_metrics()
        return metrics

    # ------------------------------------------------------------------
    # خروج پوزیشن‌ها با استفاده از داده کش‌شده
    # ------------------------------------------------------------------
    def _try_exit_cached(self, position: Dict[str, Any], decision_time: pd.Timestamp) -> bool:
        symbol = position["symbol"]
        df_5m = self._get_closed_slice_cached(symbol, config.TIMEFRAME_5M, decision_time)
        if df_5m.empty:
            return False
        candle = df_5m.iloc[-1]

        direction = position["direction"]
        sl = position["stop_loss"]
        tp = position["take_profit"]

        if direction == "LONG":
            hit_sl = candle["low"] <= sl
            hit_tp = candle["high"] >= tp
            if hit_sl and hit_tp:
                exit_price, exit_reason = sl, "SL"
            elif hit_sl:
                exit_price, exit_reason = sl, "SL"
            elif hit_tp:
                exit_price, exit_reason = tp, "TP"
            else:
                return False
        else:
            hit_sl = candle["high"] >= sl
            hit_tp = candle["low"] <= tp
            if hit_sl and hit_tp:
                exit_price, exit_reason = sl, "SL"
            elif hit_sl:
                exit_price, exit_reason = sl, "SL"
            elif hit_tp:
                exit_price, exit_reason = tp, "TP"
            else:
                return False

        self._close_position(position, exit_price, exit_reason, decision_time)
        return True

    def _close_at_end_cached(self, position: Dict[str, Any], end_date: Optional[pd.Timestamp]):
        symbol = position["symbol"]
        df_5m = self._get_data(symbol, config.TIMEFRAME_5M)
        if df_5m.empty:
            close_price = position["entry_price"]
        else:
            close_price = df_5m.iloc[-1]["close"]
        self._close_position(position, close_price, "END", pd.Timestamp.now(timezone.utc))

    # ------------------------------------------------------------------
    # Safety Check با داده کش‌شده
    # ------------------------------------------------------------------
    def _safety_check_cached(self, best: Dict[str, Any], decision_time: pd.Timestamp) -> Tuple[bool, str]:
        symbol = best.get("symbol")
        volume = self.provider.get_volume_24h_usdt(symbol, decision_time)
        if volume is None or volume < MIN_24H_VOLUME_USDT:
            return False, "Volume below minimum"
        if self.current_balance < float(best.get("risk_amount", 0)):
            return False, "Insufficient balance"
        if symbol in self.open_positions:
            return False, "Existing position"

        entry = best.get("entry_price")
        sl = best.get("stop_loss")
        tp = best.get("take_profit")
        size = best.get("position_size")
        risk = best.get("risk_amount")

        if not all(isinstance(x, (int, float)) and x > 0 for x in (entry, sl, tp, size, risk)):
            return False, "Invalid risk parameters"

        if best["signal"] == "LONG":
            if not (sl < entry < tp):
                return False, "Invalid LONG price geometry"
        else:
            if not (tp < entry < sl):
                return False, "Invalid SHORT price geometry"
        return True, "OK"

    # ------------------------------------------------------------------
    # بستن پوزیشن و محاسبه PnL
    # ------------------------------------------------------------------
    def _close_position(self, position, exit_price, exit_reason, exit_time):
        direction = position["direction"]
        entry = position["entry_price"]
        size = position["position_size"]
        risk = position["risk_amount"]

        if direction == "LONG":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        fee = self.fee_rate * abs(pnl) if pnl > 0 else 0.0
        pnl -= fee

        r_multiple = pnl / risk if risk else 0.0
        self.current_balance += pnl

        self.trades.append({
            "symbol": position["symbol"],
            "direction": direction,
            "entry_time": position["entry_time"],
            "entry_price": entry,
            "stop_loss": position["stop_loss"],
            "take_profit": position["take_profit"],
            "position_size": size,
            "risk_amount": risk,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "r_multiple": r_multiple,
            "balance_after": self.current_balance,
            "score": position.get("score"),
            "regime_4h": position.get("regime_4h"),
            "regime_1h": position.get("regime_1h"),
        })

    def _compute_metrics(self):
        metrics = calculate_metrics(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_balance=self.initial_balance,
        )
        long_trades = [t for t in self.trades if t["direction"] == "LONG"]
        short_trades = [t for t in self.trades if t["direction"] == "SHORT"]

        def _m(trades):
            if not trades:
                return {"trades":0,"win_rate":0.0,"net_profit":0.0,"profit_factor":float("inf"),"average_r":0.0}
            m = calculate_metrics(trades, [], initial_balance=None)
            return {"trades":m["total_trades"],"win_rate":m["win_rate"],"net_profit":m["net_profit"],"profit_factor":m["profit_factor"],"average_r":m["average_r"]}

        symbol_metrics = {}
        for sym in self.symbols:
            symbol_metrics[sym] = _m([t for t in self.trades if t["symbol"]==sym])

        regime_metrics = {}
        for r in ["BULLISH","BEARISH","RANGE"]:
            if r == "BULLISH":
                rt = [t for t in self.trades if t["regime_4h"]=="BULLISH" and t["regime_1h"]=="BULLISH"]
            elif r == "BEARISH":
                rt = [t for t in self.trades if t["regime_4h"]=="BEARISH" and t["regime_1h"]=="BEARISH"]
            else:
                rt = [t for t in self.trades if not ((t["regime_4h"]=="BULLISH" and t["regime_1h"]=="BULLISH") or (t["regime_4h"]=="BEARISH" and t["regime_1h"]=="BEARISH"))]
            regime_metrics[r] = _m(rt)

        period_metrics = {}
        for t in self.trades:
            key = t["exit_time"].strftime("%Y-%m") if t["exit_time"] else "unknown"
            period_metrics.setdefault(key, []).append(t)
        for k in period_metrics:
            period_metrics[k] = _m(period_metrics[k])

        return {
            "success": True,
            "period": {"start": None, "end": None},
            "symbols_scanned": len(self.symbols),
            "eligible_symbols": len(self.symbols),
            "data_quality": {},
            "total_candidates": self.candidates_count,
            "selected_signals": self.selected_count,
            "safety_rejections": self.safety_rejections,
            "total_trades": metrics["total_trades"],
            "metrics": metrics,
            "long_metrics": _m(long_trades),
            "short_metrics": _m(short_trades),
            "symbol_metrics": symbol_metrics,
            "regime_metrics": regime_metrics,
            "period_metrics": period_metrics,
            "trades": self.trades,
        }
        