"""
موتور بک‌تست chronological برای استراتژی فعلی.
فقط یک پوزیشن هم‌زمان مدیریت می‌شود و از داده‌های تاریخی بدون نگاه به آینده استفاده می‌شود.
"""

import pandas as pd
from datetime import timedelta
import config
import strategy


class BacktestEngine:
    def __init__(self, data_5m: pd.DataFrame, data_1h: pd.DataFrame,
                 data_4h: pd.DataFrame, initial_balance: float):
        self.data_5m = data_5m
        self.data_1h = data_1h
        self.data_4h = data_4h
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.equity_curve = [{"timestamp": data_5m.index[0], "balance": initial_balance}] if not data_5m.empty else []
        self.current_position = None

    def run(self) -> dict:
        """اجرای بک‌تست روی همه کندل‌های 5m."""
        if self.data_5m.empty:
            return self._build_result()

        for i in range(len(self.data_5m)):
            timestamp = self.data_5m.index[i]
            close_time = timestamp + timedelta(minutes=5)  # زمان بسته‌شدن کندل 5m

            # اگر پوزیشنی باز است، خروج احتمالی را بررسی کن
            if self.current_position is not None:
                self._check_exit(i, close_time)
                if self.current_position is not None:
                    continue  # پوزیشن باز مانده و سیگنال جدید نمی‌گیریم

            # تولید سیگنال فقط با داده‌های تا این لحظه
            df_5m_slice = self.data_5m.iloc[:i+1]
            df_1h_closed = self._filter_closed(self.data_1h, close_time, '1h')
            df_4h_closed = self._filter_closed(self.data_4h, close_time, '4h')

            signal = strategy.generate_signal(
                df_4h_closed,
                df_1h_closed,
                df_5m_slice,
                account_balance=self.balance
            )

            if signal["valid"] and signal["signal"] in ("LONG", "SHORT"):
                # ورود در همان close_time
                self._open_position(signal, close_time)

        # اگر در پایان هنوز پوزیشن باز است، با آخرین قیمت ببند
        if self.current_position is not None:
            self._close_position_at_end()

        return self._build_result()

    def _filter_closed(self, df: pd.DataFrame, as_of: pd.Timestamp, tf: str) -> pd.DataFrame:
        """فقط کندل‌هایی که زمان بسته‌شدنشان <= as_of است."""
        if df.empty:
            return df
        delta = strategy._timeframe_to_timedelta(tf)
        mask = df.index + delta <= as_of
        return df.loc[mask]

    def _open_position(self, signal: dict, entry_time: pd.Timestamp):
        self.current_position = {
            "direction": signal["signal"],
            "entry_time": entry_time,
            "entry_price": signal["entry_price"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "position_size": signal["position_size"],
            "risk_amount": signal["risk_amount"],
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "pnl": 0.0,
            "r_multiple": 0.0,
        }

    def _check_exit(self, i: int, current_time: pd.Timestamp):
        """بررسی خروج از معامله بر اساس کندل i (که کامل بسته شده)."""
        candle = self.data_5m.iloc[i]
        pos = self.current_position

        if pos["direction"] == "LONG":
            hit_sl = candle["low"] <= pos["stop_loss"]
            hit_tp = candle["high"] >= pos["take_profit"]
            if hit_sl and hit_tp:
                # SL FIRST (conservative)
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_sl:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_tp:
                exit_price = pos["take_profit"]
                exit_reason = "TP"
            else:
                return  # هنوز باز

            pnl = (exit_price - pos["entry_price"]) * pos["position_size"]
        else:  # SHORT
            hit_sl = candle["high"] >= pos["stop_loss"]
            hit_tp = candle["low"] <= pos["take_profit"]
            if hit_sl and hit_tp:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_sl:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_tp:
                exit_price = pos["take_profit"]
                exit_reason = "TP"
            else:
                return

            pnl = (pos["entry_price"] - exit_price) * pos["position_size"]

        pos["exit_price"] = exit_price
        pos["exit_time"] = current_time
        pos["exit_reason"] = exit_reason
        pos["pnl"] = pnl
        pos["r_multiple"] = pnl / pos["risk_amount"] if pos["risk_amount"] != 0 else 0.0

        self.balance += pnl
        self.trades.append(pos.copy())
        self.equity_curve.append({"timestamp": current_time, "balance": self.balance})
        self.current_position = None

    def _close_position_at_end(self):
        """بستن پوزیشن در پایان داده با آخرین قیمت موجود."""
        last_candle = self.data_5m.iloc[-1]
        pos = self.current_position
        exit_price = last_candle["close"]
        if pos["direction"] == "LONG":
            pnl = (exit_price - pos["entry_price"]) * pos["position_size"]
        else:
            pnl = (pos["entry_price"] - exit_price) * pos["position_size"]

        pos["exit_price"] = exit_price
        pos["exit_time"] = self.data_5m.index[-1] + timedelta(minutes=5)
        pos["exit_reason"] = "END"
        pos["pnl"] = pnl
        pos["r_multiple"] = pnl / pos["risk_amount"] if pos["risk_amount"] != 0 else 0.0

        self.balance += pnl
        self.trades.append(pos.copy())
        self.equity_curve.append({"timestamp": pos["exit_time"], "balance": self.balance})
        self.current_position = None

    def _build_result(self) -> dict:
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t["pnl"] > 0)
        losing_trades = sum(1 for t in self.trades if t["pnl"] <= 0)
        gross_profit = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        average_r = (sum(t["r_multiple"] for t in self.trades) / total_trades) if total_trades > 0 else 0.0

        # محاسبه Max Drawdown از equity_curve
        max_dd = 0.0
        peak = -float('inf')
        for point in self.equity_curve:
            balance = point["balance"]
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak != 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "net_profit": self.balance - self.initial_balance,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "average_r": average_r,
            "trades": self.trades,
        }
