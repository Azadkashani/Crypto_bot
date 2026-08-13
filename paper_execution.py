"""
ماژول اجرای کاغذی (Paper Execution) برای شبیه‌سازی سیگنال‌ها.

این ماژول هیچ ارتباطی با صرافی ندارد و صرفاً وضعیت معاملات کاغذی را
بر اساس سیگنال‌های تأییدشده مدیریت می‌کند.

مهم:
    - هیچ سفارش واقعی ارسال نمی‌شود.
    - هیچ API خصوصی صرافی استفاده نمی‌شود.
    - هیچ مسیر اجرای زنده وجود ندارد.
"""

from typing import Optional, Dict, Any, List
import pandas as pd

import config
from metrics import calculate_metrics


class PaperExecutionEngine:
    """
    موتور اجرای کاغذی برای مدیریت یک پوزیشن هم‌زمان.

    جریان کار:
        1. دریافت سیگنال معتبر از strategy.generate_signal()
        2. باز کردن پوزیشن کاغذی در صورت نبود پوزیشن باز
        3. پردازش کندل‌های بسته‌شده برای بررسی SL/TP
        4. بستن پوزیشن در صورت فعال شدن SL/TP یا پایان داده
        5. ثبت معاملات و به‌روزرسانی بالانس و منحنی سرمایه
    """

    def __init__(self, initial_balance: Optional[float] = None):
        """
        سازنده موتور اجرای کاغذی.

        پارامترها:
            initial_balance: سرمایه اولیه. اگر None باشد از config.ACCOUNT_BALANCE استفاده می‌شود.
        """
        if initial_balance is None:
            initial_balance = float(getattr(config, "ACCOUNT_BALANCE", 1000.0))
        self.initial_balance = float(initial_balance)
        self.current_balance = self.initial_balance
        self.open_position: Optional[Dict[str, Any]] = None
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = [
            {"timestamp": pd.Timestamp("1970-01-01", tz="UTC"), "balance": self.current_balance}
        ]
        self.last_timestamp: Optional[pd.Timestamp] = None
        self._trade_id = 0

    # ------------------------------------------------------------------
    # اعتبارسنجی زمانی
    # ------------------------------------------------------------------
    def _validate_timestamp(self, timestamp: pd.Timestamp) -> None:
        """بررسی ترتیب صعودی و عدم تکراری بودن timestamp."""
        if self.last_timestamp is not None:
            if timestamp <= self.last_timestamp:
                if timestamp == self.last_timestamp:
                    raise ValueError("Duplicate timestamp detected")
                raise ValueError("Timestamp must be after last processed timestamp")
        self.last_timestamp = timestamp

    # ------------------------------------------------------------------
    # اعتبارسنجی سیگنال
    # ------------------------------------------------------------------
    def _validate_signal(self, signal: Dict[str, Any], timestamp: pd.Timestamp) -> Dict[str, Any]:
        """بررسی کامل سیگنال و بازگرداندن نتیجه."""
        if not isinstance(signal, dict):
            return {"valid": False, "reason": "Signal must be a dictionary"}

        if signal.get("valid") is not True:
            return {"valid": False, "reason": "Signal is not valid"}

        direction = signal.get("signal")
        if direction not in ("LONG", "SHORT"):
            return {"valid": False, "reason": "Invalid signal direction"}

        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        position_size = signal.get("position_size")
        risk_amount = signal.get("risk_amount")

        # همه قیمت‌ها باید مثبت باشند
        if entry_price is None or entry_price <= 0:
            return {"valid": False, "reason": "Invalid entry price"}
        if stop_loss is None or stop_loss <= 0:
            return {"valid": False, "reason": "Invalid stop loss"}
        if take_profit is None or take_profit <= 0:
            return {"valid": False, "reason": "Invalid take profit"}
        if position_size is None or position_size <= 0:
            return {"valid": False, "reason": "Invalid position size"}
        if risk_amount is None or risk_amount <= 0:
            return {"valid": False, "reason": "Invalid risk amount"}

        # رابطه جهت و قیمت‌ها
        if direction == "LONG":
            if not (stop_loss < entry_price < take_profit):
                return {"valid": False, "reason": "LONG price relationship invalid"}
        else:  # SHORT
            if not (take_profit < entry_price < stop_loss):
                return {"valid": False, "reason": "SHORT price relationship invalid"}

        # timestamp سیگنال نباید از زمان جاری جلوتر باشد
        signal_timestamp = signal.get("timestamp")
        if signal_timestamp is not None:
            if pd.Timestamp(signal_timestamp) > timestamp:
                return {"valid": False, "reason": "Future signal timestamp"}

        return {"valid": True, "reason": "Signal valid"}

    # ------------------------------------------------------------------
    # پردازش سیگنال
    # ------------------------------------------------------------------
    def process_signal(self, signal: Dict[str, Any], timestamp: pd.Timestamp) -> Dict[str, Any]:
        """
        پردازش یک سیگنال و باز کردن پوزیشن کاغذی در صورت معتبر بودن.

        پارامترها:
            signal: دیکشنری سیگنال تولیدشده توسط strategy.generate_signal()
            timestamp: زمان جاری پردازش (باید بزرگ‌تر از آخرین زمان پردازش باشد)

        خروجی:
            dict شامل accepted و reason و position در صورت موفقیت.
        """
        # بررسی ترتیب زمانی
        self._validate_timestamp(timestamp)

        # بررسی سیگنال
        validation = self._validate_signal(signal, timestamp)
        if not validation["valid"]:
            return {"accepted": False, "reason": validation["reason"]}

        # بررسی پوزیشن باز
        if self.open_position is not None:
            return {"accepted": False, "reason": "Position already open"}

        # ثبت پوزیشن
        self._trade_id += 1
        trade_id = self._trade_id
        entry_time = pd.Timestamp(signal.get("timestamp", timestamp))

        position = {
            "trade_id": trade_id,
            "direction": signal["signal"],
            "entry_time": entry_time,
            "entry_price": float(signal["entry_price"]),
            "stop_loss": float(signal["stop_loss"]),
            "take_profit": float(signal["take_profit"]),
            "position_size": float(signal["position_size"]),
            "risk_amount": float(signal["risk_amount"]),
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "pnl": 0.0,
            "r_multiple": 0.0,
        }
        self.open_position = position

        return {
            "accepted": True,
            "reason": "Position opened",
            "position": position.copy(),
        }

    # ------------------------------------------------------------------
    # پردازش کندل
    # ------------------------------------------------------------------
    def process_candle(self, candle: Dict[str, Any], timestamp: pd.Timestamp) -> Dict[str, Any]:
        """
        پردازش یک کندل بسته‌شده و بررسی SL/TP برای پوزیشن باز.

        پارامترها:
            candle: دیکشنری شامل open, high, low, close, volume
            timestamp: زمان بسته‌شدن کندل

        خروجی:
            dict شامل accepted و reason و در صورت بسته‌شدن معامله اطلاعات خروج.
        """
        self._validate_timestamp(timestamp)

        if self.open_position is None:
            return {"accepted": False, "reason": "No open position"}

        pos = self.open_position
        direction = pos["direction"]
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        exit_price = None
        exit_reason = None

        if direction == "LONG":
            hit_sl = low <= pos["stop_loss"]
            hit_tp = high >= pos["take_profit"]
            if hit_sl and hit_tp:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_sl:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_tp:
                exit_price = pos["take_profit"]
                exit_reason = "TP"
        else:  # SHORT
            hit_sl = high >= pos["stop_loss"]
            hit_tp = low <= pos["take_profit"]
            if hit_sl and hit_tp:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_sl:
                exit_price = pos["stop_loss"]
                exit_reason = "SL"
            elif hit_tp:
                exit_price = pos["take_profit"]
                exit_reason = "TP"

        if exit_price is None:
            return {"accepted": False, "reason": "No exit triggered"}

        # بستن پوزیشن
        self._close_position(exit_price, exit_reason, timestamp)

        return {
            "accepted": True,
            "reason": f"Position closed via {exit_reason}",
            "trade": self.trades[-1].copy(),
        }

    # ------------------------------------------------------------------
    # بستن در پایان داده
    # ------------------------------------------------------------------
    def close_at_end(self, candle: Dict[str, Any], timestamp: pd.Timestamp) -> Dict[str, Any]:
        """
        بستن پوزیشن باز در پایان داده با قیمت آخرین کندل بسته‌شده.

        پارامترها:
            candle: آخرین کندل بسته‌شده
            timestamp: زمان بسته‌شدن آخرین کندل

        خروجی:
            dict شامل accepted و reason و trade در صورت بسته‌شدن.
        """
        self._validate_timestamp(timestamp)

        if self.open_position is None:
            return {"accepted": False, "reason": "No open position"}

        close_price = float(candle["close"])
        self._close_position(close_price, "END", timestamp)

        return {
            "accepted": True,
            "reason": "Position closed at end of data",
            "trade": self.trades[-1].copy(),
        }

    # ------------------------------------------------------------------
    # بستن پوزیشن و به‌روزرسانی‌ها
    # ------------------------------------------------------------------
    def _close_position(self, exit_price: float, exit_reason: str, timestamp: pd.Timestamp):
        """بستن پوزیشن، محاسبه PnL و ثبت معامله."""
        pos = self.open_position
        direction = pos["direction"]
        entry = pos["entry_price"]
        size = pos["position_size"]

        if direction == "LONG":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        risk_amount = pos["risk_amount"]
        r_multiple = pnl / risk_amount if risk_amount else 0.0

        pos["exit_time"] = timestamp
        pos["exit_price"] = exit_price
        pos["exit_reason"] = exit_reason
        pos["pnl"] = pnl
        pos["r_multiple"] = r_multiple

        self.trades.append(pos.copy())
        self.current_balance += pnl
        self.equity_curve.append({"timestamp": timestamp, "balance": self.current_balance})
        self.open_position = None

    # ------------------------------------------------------------------
    # دریافت وضعیت
    # ------------------------------------------------------------------
    def get_open_position(self) -> Optional[Dict[str, Any]]:
        """بازگرداندن پوزیشن باز فعلی."""
        return self.open_position

    def get_trades(self) -> List[Dict[str, Any]]:
        """بازگرداندن لیست معاملات بسته‌شده."""
        return self.trades

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """بازگرداندن منحنی سرمایه."""
        return self.equity_curve

    # ------------------------------------------------------------------
    # خلاصه
    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """محاسبه خلاصه عملکرد با استفاده از metrics موجود."""
        metrics = calculate_metrics(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_balance=self.initial_balance,
        )

        return {
            "initial_balance": self.initial_balance,
            "final_balance": metrics["final_balance"],
            "net_profit": metrics["net_profit"],
            "total_trades": metrics["total_trades"],
            "winning_trades": metrics["winning_trades"],
            "losing_trades": metrics["losing_trades"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "average_r": metrics["average_r"],
            "open_position": self.open_position,
        }
