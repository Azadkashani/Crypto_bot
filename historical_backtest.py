"""
Real Market Historical Backtest.

این ماژول با استفاده از داده‌های تاریخی چندنمادی و چندتایم‌فریمی،
Pipeline نهایی را شبیه‌سازی می‌کند:
    Market Eligibility → Strategy → Risk Gate → Position Sizing
    → Scoring → Ranking → Safety → Paper Execution

هیچ سفارش واقعی ارسال نمی‌شود.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime, timezone
import math

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
    """اعتبارسنجی ساختار و داده OHLCV."""
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
                issues.append("high < max(open, close)")
            if (df["low"] > df[["open", "close"]].min(axis=1)).any():
                issues.append("low > min(open, close)")
        if "volume" in df.columns and (df["volume"] < 0).any():
            issues.append("negative volume")
    return {"valid": len(issues) == 0, "issues": issues}


class HistoricalDataProvider:
    """
    Abstract provider for historical data.
    Tests use FakeHistoricalDataProvider.
    """
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[pd.Timestamp] = None,
        end: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def get_volume_24h_usdt(
        self,
        symbol: str,
        timestamp: pd.Timestamp,
    ) -> Optional[float]:
        raise NotImplementedError


class HistoricalBacktestRunner:
    """
    اجرای بک‌تست چندنمادی روی داده تاریخی.
    """

    def __init__(
        self,
        provider: HistoricalDataProvider,
        symbols: List[str],
        initial_balance: Optional[float] = None,
        fee_rate: float = 0.0,
        slippage_rate: float = 0.0,
    ):
        self.provider = provider
        self.symbols = symbols
        self.initial_balance = initial_balance or config.ACCOUNT_BALANCE
        self.current_balance = float(self.initial_balance)
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.trades: List[Dict[str, Any]] = []
        self.candidates_count = 0
        self.selected_count = 0
        self.safety_rejections = 0
        self.equity_curve: List[Dict[str, Any]] = [
            {"timestamp": None, "balance": self.current_balance}
        ]

    def _load_data(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[pd.Timestamp],
        end: Optional[pd.Timestamp],
    ) -> pd.DataFrame:
        df = self.provider.get_ohlcv(symbol, timeframe, start, end)
        validation = validate_ohlcv(df, timeframe)
        if not validation["valid"]:
            raise ValueError(
                f"Invalid OHLCV for {symbol} {timeframe}: {validation['issues']}"
            )
        return df

    def _get_closed_slice(
        self,
        df: pd.DataFrame,
        timeframe: str,
        decision_time: pd.Timestamp,
    ) -> pd.DataFrame:
        """فقط کندل‌هایی که پایان آن‌ها <= decision_time است."""
        delta = _timeframe_to_timedelta(timeframe)
        mask = df.index + delta <= decision_time
        return df.loc[mask]

    def _get_all_decision_times(self) -> List[pd.Timestamp]:
        """ترکیب زمان‌های بسته‌شدن کندل‌های 5m همه Symbolها."""
        times = set()
        for symbol in self.symbols:
            df = self.provider.get_ohlcv(
                symbol, config.TIMEFRAME_5M, None, None
            )
            if df.empty:
                continue
            delta = _timeframe_to_timedelta(config.TIMEFRAME_5M)
            times.update(df.index + delta)
        return sorted(times)

    def run(
        self,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
    ) -> Dict[str, Any]:
        """
        اجرای کامل بک‌تست تاریخی.

        خروجی شامل معیارهای اصلی و تحلیل‌های تفکیکی است.
        """
        # اعتبارسنجی داده اولیه برای همه Symbol/timeframe
        data_quality_report: Dict[str, Any] = {}
        for symbol in self.symbols:
            for tf in [config.TIMEFRAME_4H, config.TIMEFRAME_1H, config.TIMEFRAME_5M]:
                df = self.provider.get_ohlcv(symbol, tf, start_date, end_date)
                validation = validate_ohlcv(df, tf)
                data_quality_report[f"{symbol}:{tf}"] = validation

        decision_times = self._get_all_decision_times()

        open_position: Optional[Dict[str, Any]] = None

        for decision_time in decision_times:
            if start_date is not None and decision_time < start_date:
                continue
            if end_date is not None and decision_time > end_date:
                continue

            # اگر پوزیشنی باز است، خروج احتمالی را بررسی کن
            if open_position is not None:
                closed = self._try_exit(open_position, decision_time)
                if closed:
                    open_position = None

            if open_position is not None:
                # با یک پوزیشن باز سیگنال جدید نمی‌گیریم
                continue

            candidates: List[Dict[str, Any]] = []

            for symbol in self.symbols:
                # Volume historical / eligibility
                volume = self.provider.get_volume_24h_usdt(symbol, decision_time)
                if volume is None or volume < MIN_24H_VOLUME_USDT:
                    continue

                try:
                    df_4h = self._get_closed_slice(
                        self.provider.get_ohlcv(symbol, config.TIMEFRAME_4H, start_date, end_date),
                        config.TIMEFRAME_4H,
                        decision_time,
                    )
                    df_1h = self._get_closed_slice(
                        self.provider.get_ohlcv(symbol, config.TIMEFRAME_1H, start_date, end_date),
                        config.TIMEFRAME_1H,
                        decision_time,
                    )
                    df_5m = self._get_closed_slice(
                        self.provider.get_ohlcv(symbol, config.TIMEFRAME_5M, start_date, end_date),
                        config.TIMEFRAME_5M,
                        decision_time,
                    )
                except Exception:
                    continue

                signal = strategy.generate_signal(
                    df_4h,
                    df_1h,
                    df_5m,
                    as_of=decision_time,
                    account_balance=self.current_balance,
                    symbol=symbol,
                )

                if signal.get("valid") is not True:
                    continue
                if signal.get("signal") not in ("LONG", "SHORT"):
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

            ranked = signal_scoring.rank_signals(candidates)
            best = ranked[0]
            self.selected_count += 1

            # Safety: volume recheck, balance, no position
            volume_now = self.provider.get_volume_24h_usdt(best["symbol"], decision_time)
            if volume_now is None or volume_now < MIN_24H_VOLUME_USDT:
                self.safety_rejections += 1
                continue
            if self.current_balance <= 0:
                self.safety_rejections += 1
                continue

            # باز کردن پوزیشن کاغذی
            entry_price = best.get("entry_price")
            sl = best.get("stop_loss")
            tp = best.get("take_profit")
            size = best.get("position_size")
            risk_amount = best.get("risk_amount")

            if not all(isinstance(x, (int, float)) and x > 0 for x in (entry_price, sl, tp, size, risk_amount)):
                self.safety_rejections += 1
                continue

            # اعمال slippage بر قیمت ورود
            if best["signal"] == "LONG":
                fill_price = entry_price * (1 + self.slippage_rate)
            else:
                fill_price = entry_price * (1 - self.slippage_rate)

            open_position = {
                "symbol": best["symbol"],
                "direction": best["signal"],
                "entry_time": decision_time,
                "entry_price": float(fill_price),
                "stop_loss": float(sl),
                "take_profit": float(tp),
                "position_size": float(size),
                "risk_amount": float(risk_amount),
                "score": best.get("score"),
                "regime_4h": best.get("regime_4h"),
                "regime_1h": best.get("regime_1h"),
            }

        # بستن پوزیشن باز در پایان داده
        if open_position is not None:
            self._close_at_end(open_position, end_date)

        # ساخت equity curve نهایی
        equity_times = []
        balances = []
        for trade in self.trades:
            equity_times.append(trade["exit_time"])
            balances.append(trade["balance_after"])
        if equity_times:
            self.equity_curve = [
                {"timestamp": t, "balance": b}
                for t, b in zip(equity_times, balances)
            ]

        metrics = calculate_metrics(
            trades=[t for t in self.trades],
            equity_curve=self.equity_curve,
            initial_balance=self.initial_balance,
        )

        long_trades = [t for t in self.trades if t["direction"] == "LONG"]
        short_trades = [t for t in self.trades if t["direction"] == "SHORT"]

        def _metrics_for(trades):
            if not trades:
                return {
                    "trades": 0,
                    "win_rate": 0.0,
                    "net_profit": 0.0,
                    "profit_factor": float("inf"),
                    "average_r": 0.0,
                }
            m = calculate_metrics(trades, [], initial_balance=None)
            return {
                "trades": m["total_trades"],
                "win_rate": m["win_rate"],
                "net_profit": m["net_profit"],
                "profit_factor": m["profit_factor"],
                "average_r": m["average_r"],
            }

        symbol_metrics = {}
        for sym in self.symbols:
            sym_trades = [t for t in self.trades if t["symbol"] == sym]
            symbol_metrics[sym] = _metrics_for(sym_trades)

        regime_metrics = {}
        for regime_name in ["BULLISH", "BEARISH", "RANGE"]:
            if regime_name == "BULLISH":
                regime_trades = [t for t in self.trades if t["regime_4h"] == "BULLISH" and t["regime_1h"] == "BULLISH"]
            elif regime_name == "BEARISH":
                regime_trades = [t for t in self.trades if t["regime_4h"] == "BEARISH" and t["regime_1h"] == "BEARISH"]
            else:
                regime_trades = [t for t in self.trades if not (
                    (t["regime_4h"] == "BULLISH" and t["regime_1h"] == "BULLISH") or
                    (t["regime_4h"] == "BEARISH" and t["regime_1h"] == "BEARISH")
                )]
            regime_metrics[regime_name] = _metrics_for(regime_trades)

        # بازه‌های زمانی ماهانه
        period_metrics = {}
        for trade in self.trades:
            month_key = trade["exit_time"].strftime("%Y-%m") if trade["exit_time"] else "unknown"
            period_metrics.setdefault(month_key, []).append(trade)
        for key in period_metrics:
            period_metrics[key] = _metrics_for(period_metrics[key])

        return {
            "success": True,
            "period": {
                "start": start_date,
                "end": end_date,
            },
            "symbols_scanned": len(self.symbols),
            "eligible_symbols": len(self.symbols),
            "data_quality": data_quality_report,
            "total_candidates": self.candidates_count,
            "selected_signals": self.selected_count,
            "safety_rejections": self.safety_rejections,
            "total_trades": metrics["total_trades"],
            "metrics": metrics,
            "long_metrics": _metrics_for(long_trades),
            "short_metrics": _metrics_for(short_trades),
            "symbol_metrics": symbol_metrics,
            "regime_metrics": regime_metrics,
            "period_metrics": period_metrics,
            "trades": self.trades,
        }

    def _try_exit(self, position: Dict[str, Any], decision_time: pd.Timestamp) -> bool:
        """بررسی SL/TP با قانون SL FIRST. True یعنی پوزیشن بسته شده."""
        symbol = position["symbol"]
        try:
            df_5m = self.provider.get_ohlcv(symbol, config.TIMEFRAME_5M, None, decision_time)
            if df_5m.empty:
                return False
            df_5m = self._get_closed_slice(df_5m, config.TIMEFRAME_5M, decision_time)
            if df_5m.empty:
                return False
            candle = df_5m.iloc[-1]
        except Exception:
            return False

        direction = position["direction"]
        sl = position["stop_loss"]
        tp = position["take_profit"]

        if direction == "LONG":
            hit_sl = candle["low"] <= sl
            hit_tp = candle["high"] >= tp
            if hit_sl and hit_tp:
                exit_price = sl
                exit_reason = "SL"
            elif hit_sl:
                exit_price = sl
                exit_reason = "SL"
            elif hit_tp:
                exit_price = tp
                exit_reason = "TP"
            else:
                return False
        else:
            hit_sl = candle["high"] >= sl
            hit_tp = candle["low"] <= tp
            if hit_sl and hit_tp:
                exit_price = sl
                exit_reason = "SL"
            elif hit_sl:
                exit_price = sl
                exit_reason = "SL"
            elif hit_tp:
                exit_price = tp
                exit_reason = "TP"
            else:
                return False

        self._close_position(position, exit_price, exit_reason, decision_time)
        return True

    def _close_at_end(self, position: Dict[str, Any], end_date: Optional[pd.Timestamp]):
        symbol = position["symbol"]
        try:
            df_5m = self.provider.get_ohlcv(symbol, config.TIMEFRAME_5M, None, end_date)
            if df_5m.empty:
                df_5m = self.provider.get_ohlcv(symbol, config.TIMEFRAME_5M, None, None)
            if df_5m.empty:
                return
            close_price = df_5m.iloc[-1]["close"]
        except Exception:
            close_price = position["entry_price"]
        self._close_position(position, close_price, "END", pd.Timestamp.now(timezone.utc))

    def _close_position(
        self,
        position: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        exit_time: pd.Timestamp,
    ):
        direction = position["direction"]
        entry = position["entry_price"]
        size = position["position_size"]
        risk = position["risk_amount"]

        if direction == "LONG":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        # کسر fee
        fee = self.fee_rate * abs(pnl) if pnl > 0 else 0.0
        pnl -= fee

        r_multiple = pnl / risk if risk else 0.0

        self.current_balance += pnl

        trade = {
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
        }
        self.trades.append(trade)
