"""
Backtest Engine با دو کلاس:
- OptimizedBacktestRunner (نسخه بهینه‌شده با پیش‌محاسبه)
- BacktestEngine (رابط قدیمی برای سازگاری با تست‌های فاز ۱۰ و ۱۲)

هیچ تغییر منطقی در استراتژی، Risk، Scoring یا SL/TP ایجاد نشده است.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

import config
import strategy
import signal_scoring
from metrics import calculate_metrics
from indicators import add_rsi, add_ema, add_adx, detect_swings
from regime import get_regime
from choch import detect_choch
from bos import detect_bos


class SimpleDataProvider:
    """Provider ساده برای سازگاری با interface قدیمی BacktestEngine."""
    def __init__(self, data_5m, data_1h, data_4h, volumes=None, symbol='BTC/USDT:USDT'):
        self.symbols = [symbol]
        self.data = {
            symbol: {
                '5m': data_5m,
                '1h': data_1h,
                '4h': data_4h,
            }
        }
        if volumes is None:
            volumes = {symbol: 2_000_000.0}
        self.volumes = volumes

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe, pd.DataFrame())
        if start is not None:
            df = df[df.index >= start]
        if end is not None:
            df = df[df.index <= end]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volumes.get(symbol)


class OptimizedBacktestRunner:
    """
    نسخهٔ بهینه‌شده با پیش‌محاسبه‌ی کامل اندیکاتورها.
    """

    def __init__(
        self,
        provider,
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
        self._precomputed: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # پیش‌محاسبه
    # ------------------------------------------------------------------
    def _precompute_symbol(self, symbol: str) -> None:
        data = {}
        for tf in [config.TIMEFRAME_4H, config.TIMEFRAME_1H, config.TIMEFRAME_5M]:
            df = self.provider.get_ohlcv(symbol, tf, None, None)
            if df.empty:
                data[tf] = {
                    "index": np.array([], dtype="datetime64[ns]"),
                    "df": df,
                }
                continue

            df = df.sort_index()
            index_arr = df.index.values.astype("datetime64[ns]")
            enriched = df.copy()

            if tf == config.TIMEFRAME_5M:
                enriched = add_rsi(enriched, period=config.RSI_PERIOD)
                enriched = detect_swings(enriched)
                enriched = detect_choch(enriched)
                enriched = detect_bos(enriched)

                rsi_series = enriched[f"rsi_{config.RSI_PERIOD}"].to_numpy(dtype="float64")
                swing_high = enriched["swing_high"].to_numpy(dtype="bool")
                swing_low = enriched["swing_low"].to_numpy(dtype="bool")
                bullish_choch = enriched["bullish_choch"].to_numpy(dtype="bool")
                bearish_choch = enriched["bearish_choch"].to_numpy(dtype="bool")
                bullish_bos = enriched["bullish_bos"].to_numpy(dtype="bool")
                bearish_bos = enriched["bearish_bos"].to_numpy(dtype="bool")
                close_arr = enriched["close"].to_numpy(dtype="float64")
                high_arr = enriched["high"].to_numpy(dtype="float64")
                low_arr = enriched["low"].to_numpy(dtype="float64")
                open_arr = enriched["open"].to_numpy(dtype="float64")
                volume_arr = enriched["volume"].to_numpy(dtype="float64")

                data[tf] = {
                    "index": index_arr,
                    "close": close_arr,
                    "high": high_arr,
                    "low": low_arr,
                    "open": open_arr,
                    "volume": volume_arr,
                    "rsi": rsi_series,
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                    "bullish_choch": bullish_choch,
                    "bearish_choch": bearish_choch,
                    "bullish_bos": bullish_bos,
                    "bearish_bos": bearish_bos,
                }
            else:
                ema_fast_arr = add_ema(enriched, config.EMA_FAST, "close", "ema_fast")["ema_fast"].to_numpy()
                ema_mid_arr = add_ema(enriched, config.EMA_MID, "close", "ema_mid")["ema_mid"].to_numpy()
                ema_slow_arr = add_ema(enriched, config.EMA_SLOW, "close", "ema_slow")["ema_slow"].to_numpy()
                adx_arr = add_adx(enriched, config.ADX_PERIOD, "adx")["adx"].to_numpy()

                regime_arr = np.full(len(df), "RANGE", dtype=object)
                close_vals = enriched["close"].to_numpy(dtype="float64")
                for i in range(len(df)):
                    if np.isnan(ema_fast_arr[i]) or np.isnan(ema_mid_arr[i]) or np.isnan(ema_slow_arr[i]) or np.isnan(adx_arr[i]):
                        continue
                    if (
                        ema_fast_arr[i] > ema_mid_arr[i] > ema_slow_arr[i]
                        and close_vals[i] > ema_fast_arr[i]
                        and adx_arr[i] >= config.ADX_MIN_TREND
                    ):
                        regime_arr[i] = "BULLISH"
                    elif (
                        ema_fast_arr[i] < ema_mid_arr[i] < ema_slow_arr[i]
                        and close_vals[i] < ema_fast_arr[i]
                        and adx_arr[i] >= config.ADX_MIN_TREND
                    ):
                        regime_arr[i] = "BEARISH"

                data[tf] = {
                    "index": index_arr,
                    "regime": regime_arr,
                }

        self._precomputed[symbol] = data

    def _latest_value_at(self, symbol: str, tf: str, decision_time: pd.Timestamp, key: str):
        data = self._precomputed[symbol][tf]
        arr = data.get(key)
        if arr is None or len(arr) == 0:
            return None
        idx = np.searchsorted(data["index"], decision_time.to_datetime64(), side="right") - 1
        if idx < 0:
            return None
        val = arr[idx]
        if isinstance(val, float) and np.isnan(val):
            return None
        return val

    def _get_precomputed_candle(self, symbol: str, tf: str, decision_time: pd.Timestamp) -> Optional[Dict[str, Any]]:
        data = self._precomputed[symbol][tf]
        idx = np.searchsorted(data["index"], decision_time.to_datetime64(), side="right") - 1
        if idx < 0:
            return None
        return {
            "open": data["open"][idx],
            "high": data["high"][idx],
            "low": data["low"][idx],
            "close": data["close"][idx],
            "volume": data["volume"][idx],
        }

    def _check_signal_fast(self, symbol: str, decision_time: pd.Timestamp) -> Optional[Dict[str, Any]]:
        r4h = self._latest_value_at(symbol, config.TIMEFRAME_4H, decision_time, "regime")
        r1h = self._latest_value_at(symbol, config.TIMEFRAME_1H, decision_time, "regime")
        if r4h is None or r1h is None:
            return None

        if r4h == "BULLISH" and r1h == "BULLISH":
            direction = "LONG"
            is_bullish = True
        elif r4h == "BEARISH" and r1h == "BEARISH":
            direction = "SHORT"
            is_bullish = False
        else:
            return None

        data_5m = self._precomputed[symbol][config.TIMEFRAME_5M]
        idx = np.searchsorted(data_5m["index"], decision_time.to_datetime64(), side="right") - 1
        if idx < 0:
            return None

        rsi_arr = data_5m["rsi"]
        if idx < 2 or np.isnan(rsi_arr[idx]):
            return None

        latest_rsi = rsi_arr[idx]
        prev_rsi = rsi_arr[idx - 1]

        if is_bullish:
            if latest_rsi <= prev_rsi:
                return None
            zone = rsi_arr[: idx + 1] <= config.RSI_OVERSOLD
            if not zone.any():
                return None
        else:
            if latest_rsi >= prev_rsi:
                return None
            zone = rsi_arr[: idx + 1] >= config.RSI_OVERBOUGHT
            if not zone.any():
                return None

        if is_bullish:
            choch_flags = data_5m["bullish_choch"][: idx + 1]
            bos_flags = data_5m["bullish_bos"][: idx + 1]
        else:
            choch_flags = data_5m["bearish_choch"][: idx + 1]
            bos_flags = data_5m["bearish_bos"][: idx + 1]

        if not choch_flags.any() or not bos_flags.any():
            return None

        candle = self._get_precomputed_candle(symbol, config.TIMEFRAME_5M, decision_time)
        if candle is None:
            return None

        swing_arr = data_5m["swing_low"] if is_bullish else data_5m["swing_high"]
        swing_indices = np.where(swing_arr[: idx + 1])[0]
        if len(swing_indices) == 0:
            return None
        swing_idx = swing_indices[-1]

        entry_price = float(candle["close"])
        if is_bullish:
            stop_loss = float(data_5m["low"][swing_idx])
        else:
            stop_loss = float(data_5m["high"][swing_idx])

        if stop_loss >= entry_price and is_bullish:
            return None
        if stop_loss <= entry_price and not is_bullish:
            return None

        risk = abs(entry_price - stop_loss)
        if risk <= 0:
            return None
        take_profit = entry_price + risk * config.RISK_REWARD if is_bullish else entry_price - risk * config.RISK_REWARD

        from position_sizing import calculate_position_size
        pos = calculate_position_size(
            account_balance=self.current_balance,
            risk_per_trade=config.RISK_PER_TRADE,
            entry_price=entry_price,
            stop_loss=stop_loss,
            allocation=config.POSITION_ALLOCATION,
            max_leverage=config.MAX_LEVERAGE,
        )
        if not pos["valid"]:
            return None

        return {
            "signal": direction,
            "valid": True,
            "reason": f"{direction} signal valid",
            "timeframe": "5m",
            "regime_4h": r4h,
            "regime_1h": r1h,
            "rsi_5m": float(latest_rsi),
            "rsi_recovery": True,
            "choch": True,
            "bos": True,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": config.RISK_REWARD,
            "risk_amount": pos["risk_amount"],
            "margin_allocation": pos["margin_allocation"],
            "margin_required": pos["margin_required"],
            "required_leverage": pos["required_leverage"],
            "leverage": pos["leverage"],
            "notional_position_value": pos["notional_position_value"],
            "position_size": pos["position_size"],
            "position_value": pos["position_value"],
            "stop_distance": pos["stop_distance"],
            "expected_loss_at_sl": pos["expected_loss_at_sl"],
            "timestamp": decision_time,
            "symbol": symbol,
        }

    def run(self, start_date=None, end_date=None) -> Dict[str, Any]:
        for symbol in self.symbols:
            self._precompute_symbol(symbol)

        decision_times = set()
        for symbol in self.symbols:
            idx_arr = self._precomputed[symbol][config.TIMEFRAME_5M]["index"]
            if len(idx_arr) > 0:
                delta = pd.Timedelta(minutes=5)
                decision_times.update(pd.to_datetime(idx_arr) + delta)
        decision_times = sorted(decision_times)

        for decision_time in decision_times:
            if start_date is not None and decision_time < start_date:
                continue
            if end_date is not None and decision_time > end_date:
                continue

            for sym in list(self.open_positions.keys()):
                closed = self._try_exit_fast(self.open_positions[sym], decision_time)
                if closed:
                    del self.open_positions[sym]

            if len(self.open_positions) >= self.max_positions:
                continue

            candidates = []
            for symbol in self.symbols:
                if symbol in self.open_positions:
                    continue

                volume = self.provider.get_volume_24h_usdt(symbol, decision_time)
                if volume is None or volume < 1_000_000:
                    continue

                signal = self._check_signal_fast(symbol, decision_time)
                if signal is None:
                    continue

                candidate = {**signal, "volume_24h_usdt": volume}
                score = signal_scoring.calculate_score(candidate)
                if score is None:
                    continue
                candidate["score"] = score
                candidates.append(candidate)

            if not candidates:
                continue

            self.candidates_count += len(candidates)

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
                ok, reason = self._safety_check_fast(best, decision_time)
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

        for sym in list(self.open_positions.keys()):
            self._close_at_end_fast(self.open_positions[sym], end_date)
            del self.open_positions[sym]

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

        return self._compute_metrics()

    def _try_exit_fast(self, position, decision_time):
        symbol = position["symbol"]
        candle = self._get_precomputed_candle(symbol, config.TIMEFRAME_5M, decision_time)
        if candle is None:
            return False

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

    def _close_at_end_fast(self, position, end_date):
        symbol = position["symbol"]
        idx_arr = self._precomputed[symbol][config.TIMEFRAME_5M]["index"]
        if len(idx_arr) == 0:
            close_price = position["entry_price"]
        else:
            close_price = float(self._precomputed[symbol][config.TIMEFRAME_5M]["close"][-1])
        self._close_position(position, close_price, "END", pd.Timestamp.now(timezone.utc))

    def _safety_check_fast(self, best, decision_time):
        symbol = best.get("symbol")
        volume = self.provider.get_volume_24h_usdt(symbol, decision_time)
        if volume is None or volume < 1_000_000:
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
            "entry_time": position.get("entry_time", exit_time),
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
            # کلیدهای سطح بالا برای سازگاری با BacktestEngine قدیمی
            "success": True,
            "period": {"start": None, "end": None},
            "initial_balance": self.initial_balance,
            "final_balance": metrics["final_balance"],
            "net_profit": metrics["net_profit"],
            "total_trades": metrics["total_trades"],
            "winning_trades": metrics["winning_trades"],
            "losing_trades": metrics["losing_trades"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "max_drawdown": metrics["max_drawdown"],
            "average_r": metrics["average_r"],
            "expectancy": metrics["expectancy"],
            "largest_win": metrics["largest_win"],
            "largest_loss": metrics["largest_loss"],
            "symbols_scanned": len(self.symbols),
            "eligible_symbols": len(self.symbols),
            "data_quality": {},
            "total_candidates": self.candidates_count,
            "selected_signals": self.selected_count,
            "safety_rejections": self.safety_rejections,
            "metrics": metrics,
            "long_metrics": _m(long_trades),
            "short_metrics": _m(short_trades),
            "symbol_metrics": symbol_metrics,
            "regime_metrics": regime_metrics,
            "period_metrics": period_metrics,
            "trades": self.trades,
        }


class BacktestEngine(OptimizedBacktestRunner):
    """
    نسخه سازگار با interface قدیمی (data_5m, data_1h, data_4h, initial_balance).
    """
    def __init__(self, data_5m, data_1h, data_4h, initial_balance=1000.0):
        provider = SimpleDataProvider(data_5m, data_1h, data_4h)
        super().__init__(
            provider,
            provider.symbols,
            initial_balance=initial_balance,
        )
