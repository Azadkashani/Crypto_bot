"""
لایه اجرای واقعی سفارش برای Gate.io USDT-M Perpetual Futures.

این ماژول اولین لایه‌ای است که مجاز به ارسال سفارش واقعی به صرافی است،
اما فقط در صورتی که LIVE_TRADING_ENABLED صریحاً true باشد و تمام گیت‌های
ایمنی پاس شوند.

مهم:
    - ورود به حالت live فقط با تنظیم صریح خارجی انجام می‌شود.
    - هیچ سفارشی روی import یا به‌صورت خودکار ارسال نمی‌شود.
    - تمام سفارش‌های محافظتی (SL/TP) reduce-only هستند.
    - در صورت ابهام، رفتار fail-closed اعمال می‌شود.
"""

from __future__ import annotations

import os
import math
from typing import Optional, Dict, Any, List
import pandas as pd

import config
from gate_exchange import GateExchange, MIN_24H_VOLUME_USDT


# ----------------------------------------------------------------------
# تنظیمات live
# ----------------------------------------------------------------------
# مقدار پیش‌فرض از متغیر محیطی خوانده می‌شود؛ اگر موجود نبود، False است.
# هرگز به‌صورت خودکار true نمی‌شود.
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# اگر config صراحتاً مقدار داشت، آن را در نظر بگیر
if hasattr(config, "LIVE_TRADING_ENABLED"):
    LIVE_TRADING_ENABLED = bool(config.LIVE_TRADING_ENABLED)


class ExecutionEngine:
    """
    موتور اجرای واقعی سفارش با گیت‌های ایمنی چندلایه.
    """

    def __init__(self, exchange: GateExchange, live_trading_enabled: Optional[bool] = None):
        """
        پارامترها:
            exchange: نمونه GateExchange (یا FakeExchange برای تست)
            live_trading_enabled: اگر None باشد، از ثابت LIVE_TRADING_ENABLED استفاده می‌شود.
        """
        self.exchange = exchange
        self.live_trading_enabled = (
            LIVE_TRADING_ENABLED if live_trading_enabled is None else live_trading_enabled
        )
        self.last_orders = []          # برای ثبت شناسه سفارش‌ها (بدون اطلاعات حساس)
        self._duplicate_guard = set()  # نگهبان درون‌حافظه‌ای برای جلوگیری از ارسال تکراری

    # ------------------------------------------------------------------
    # گیت‌های عمومی
    # ------------------------------------------------------------------
    def _is_live_enabled(self) -> bool:
        return self.live_trading_enabled

    def _validate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """بررسی اولیه سیگنال."""
        if not isinstance(signal, dict):
            return {"valid": False, "reason": "Signal must be a dictionary"}
        if signal.get("valid") is not True:
            return {"valid": False, "reason": "Signal is not valid"}
        direction = signal.get("signal")
        if direction not in ("LONG", "SHORT"):
            return {"valid": False, "reason": "Invalid signal direction"}
        return {"valid": True, "direction": direction}

    def _validate_prices(self, direction: str, entry: float, sl: float, tp: float) -> Dict[str, Any]:
        """بررسی روابط قیمتی."""
        if not all(isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)
                   for x in (entry, sl, tp)):
            return {"valid": False, "reason": "Invalid price values"}
        if entry <= 0 or sl <= 0 or tp <= 0:
            return {"valid": False, "reason": "Prices must be positive"}
        if direction == "LONG":
            if not (sl < entry < tp):
                return {"valid": False, "reason": "LONG price relationship invalid"}
        else:  # SHORT
            if not (tp < entry < sl):
                return {"valid": False, "reason": "SHORT price relationship invalid"}
        return {"valid": True}

    def _validate_position_size(self, size: float) -> Dict[str, Any]:
        if not isinstance(size, (int, float)) or math.isnan(size) or math.isinf(size):
            return {"valid": False, "reason": "Invalid position size"}
        if size <= 0:
            return {"valid": False, "reason": "Position size must be positive"}
        return {"valid": True}

    def _validate_risk_amount(self, risk: float, expected_risk: float) -> Dict[str, Any]:
        if not isinstance(risk, (int, float)) or math.isnan(risk) or math.isinf(risk):
            return {"valid": False, "reason": "Invalid risk amount"}
        if risk <= 0:
            return {"valid": False, "reason": "Risk amount must be positive"}
        if risk > expected_risk * 1.001:  # تحمل خطای کوچک
            return {"valid": False, "reason": "Risk amount exceeds allowed maximum"}
        return {"valid": True}

    def _validate_leverage(self, leverage: float) -> Dict[str, Any]:
        if leverage is None:
            return {"valid": False, "reason": "Leverage not provided"}
        if not isinstance(leverage, (int, float)) or math.isnan(leverage) or math.isinf(leverage):
            return {"valid": False, "reason": "Invalid leverage"}
        if leverage <= 0:
            return {"valid": False, "reason": "Leverage must be positive"}
        if hasattr(config, "LEVERAGE") and leverage > config.LEVERAGE:
            return {"valid": False, "reason": f"Leverage exceeds configured maximum ({config.LEVERAGE})"}
        return {"valid": True}

    def _check_market_eligibility(self, symbol: str) -> Dict[str, Any]:
        """بررسی بازار و حجم ۲۴ ساعته در لحظه اجرا."""
        try:
            # استفاده از متد امن موجود در GateExchange
            result = self.exchange.is_market_eligible(symbol)
            if not result.get("eligible"):
                return {"valid": False, "reason": result.get("reason", "Market not eligible")}
            return {"valid": True, "volume": result.get("volume_24h_usdt")}
        except Exception as e:
            return {"valid": False, "reason": f"Market eligibility check failed: {str(e)}"}

    def _check_balance(self, risk_amount: float) -> Dict[str, Any]:
        """دریافت بالانس و بررسی کافی بودن."""
        try:
            balance = self.exchange.get_balance()
            total = balance.get("total")
            if total is None or total <= 0:
                return {"valid": False, "reason": "Balance unavailable"}
            if total < risk_amount:
                return {"valid": False, "reason": "Insufficient balance"}
            return {"valid": True, "balance": total}
        except Exception as e:
            return {"valid": False, "reason": f"Balance check failed: {str(e)}"}

    def _check_existing_positions(self, symbol: str) -> Dict[str, Any]:
        """بررسی پوزیشن‌های باز برای نماد."""
        try:
            positions = self.exchange.get_positions()
            for pos in positions:
                if pos.get("symbol") == symbol and pos.get("contracts") not in (0, None):
                    return {"valid": False, "reason": "Existing position for symbol"}
            return {"valid": True}
        except Exception as e:
            return {"valid": False, "reason": f"Position check failed: {str(e)}"}

    def _check_quantity_precision(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """بررسی دقت و حداقل مقدار بر اساس متادیتا بازار."""
        try:
            market = self.exchange.get_market(symbol)
            precision = market.get("precision", {}).get("amount")
            limits = market.get("limits", {})
            min_amount = limits.get("amount", {}).get("min")
            min_cost = limits.get("cost", {}).get("min")

            if precision is not None:
                # گرد کردن به سمت پایین برای جلوگیری از افزایش ریسک
                import decimal
                d = decimal.Decimal(str(quantity))
                step = decimal.Decimal(str(precision))
                rounded = float(d.quantize(step, rounding=decimal.ROUND_DOWN))
                if rounded <= 0:
                    return {"valid": False, "reason": "Quantity rounded to zero"}
                # استفاده از مقدار گردشده
                if min_amount is not None and rounded < min_amount:
                    return {"valid": False, "reason": "Quantity below minimum amount"}
                if min_cost is not None:
                    # نیاز به قیمت داریم که اینجا مقدار last را فرض می‌کنیم
                    ticker = self.exchange.get_ticker(symbol)
                    last = ticker.get("last")
                    if last is not None and rounded * last < min_cost:
                        return {"valid": False, "reason": "Notional below minimum cost"}
                return {"valid": True, "rounded_quantity": rounded}
            else:
                return {"valid": False, "reason": "No amount precision information"}
        except Exception as e:
            return {"valid": False, "reason": f"Quantity precision check failed: {str(e)}"}

    def _check_duplicate_order(self, signal_hash: str) -> Dict[str, Any]:
        if signal_hash in self._duplicate_guard:
            return {"valid": False, "reason": "Duplicate order detected"}
        return {"valid": True}

    # ------------------------------------------------------------------
    # اجرای سفارش
    # ------------------------------------------------------------------
    def execute(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        اجرای کامل سیگنال معتبر در صورت پاس شدن تمام گیت‌ها.

        خروجی:
            dict با ساختار مشخص شامل success, executed, reason و در صورت موفقیت،
            شناسه سفارش‌ها و قیمت‌های محافظتی.
        """
        # 1. بررسی live
        if not self._is_live_enabled():
            return {
                "success": False,
                "executed": False,
                "reason": "Live trading disabled",
            }

        # 2. بررسی سیگنال
        signal_check = self._validate_signal(signal)
        if not signal_check["valid"]:
            return {
                "success": False,
                "executed": False,
                "reason": signal_check["reason"],
            }
        direction = signal_check["direction"]

        # 3. بررسی قیمت‌ها
        entry = signal.get("entry_price")
        sl = signal.get("stop_loss")
        tp = signal.get("take_profit")
        price_check = self._validate_prices(direction, entry, sl, tp)
        if not price_check["valid"]:
            return {"success": False, "executed": False, "reason": price_check["reason"]}

        # 4. بررسی حجم و ریسک
        position_size = signal.get("position_size")
        size_check = self._validate_position_size(position_size)
        if not size_check["valid"]:
            return {"success": False, "executed": False, "reason": size_check["reason"]}

        risk_amount = signal.get("risk_amount")
        account_balance = config.ACCOUNT_BALANCE if hasattr(config, "ACCOUNT_BALANCE") else 1000.0
        expected_risk = account_balance * config.RISK_PER_TRADE if hasattr(config, "RISK_PER_TRADE") else 0.0
        risk_check = self._validate_risk_amount(risk_amount, expected_risk)
        if not risk_check["valid"]:
            return {"success": False, "executed": False, "reason": risk_check["reason"]}

        leverage = signal.get("leverage", config.LEVERAGE)
        lev_check = self._validate_leverage(leverage)
        if not lev_check["valid"]:
            return {"success": False, "executed": False, "reason": lev_check["reason"]}

        symbol = signal.get("symbol") or config.SYMBOL
        if not symbol:
            return {"success": False, "executed": False, "reason": "Missing symbol"}

        # 5. بازار و حجم
        market_check = self._check_market_eligibility(symbol)
        if not market_check["valid"]:
            return {"success": False, "executed": False, "reason": market_check["reason"]}

        # 6. بالانس
        balance_check = self._check_balance(risk_amount)
        if not balance_check["valid"]:
            return {"success": False, "executed": False, "reason": balance_check["reason"]}

        # 7. پوزیشن‌های موجود
        position_check = self._check_existing_positions(symbol)
        if not position_check["valid"]:
            return {"success": False, "executed": False, "reason": position_check["reason"]}

        # 8. دقت مقدار
        precision_result = self._check_quantity_precision(symbol, position_size)
        if not precision_result["valid"]:
            return {"success": False, "executed": False, "reason": precision_result["reason"]}
        rounded_quantity = precision_result.get("rounded_quantity", position_size)

        # 9. جلوگیری از سفارش تکراری (هش از سیگنال)
        signal_hash = f"{symbol}:{direction}:{entry}:{sl}:{tp}:{rounded_quantity}"
        duplicate_check = self._check_duplicate_order(signal_hash)
        if not duplicate_check["valid"]:
            return {"success": False, "executed": False, "reason": duplicate_check["reason"]}

        # 10. ثبت در نگهبان تکراری
        self._duplicate_guard.add(signal_hash)

        # 11. ارسال سفارش ورود
        try:
            order_side = "buy" if direction == "LONG" else "sell"
            entry_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="market",
                side=order_side,
                amount=rounded_quantity,
                params={"reduceOnly": False},
            )
        except Exception as e:
            # در صورت خطا، نگهبان را پاک کن (چون سفارش ارسال نشد)
            self._duplicate_guard.discard(signal_hash)
            return {
                "success": False,
                "executed": False,
                "reason": f"Entry order failed: {str(e)}",
            }

        # 12. دریافت اطلاعات fill
        try:
            order_info = self.exchange.exchange.fetch_order(entry_order["id"], symbol)
            filled = order_info.get("filled", 0)
            avg_price = order_info.get("average") or order_info.get("price")
            status = order_info.get("status")
        except Exception:
            filled = rounded_quantity  # فرض fill کامل اگر امکان دریافت نبود
            avg_price = entry
            status = "closed"

        if status == "rejected":
            return {
                "success": False,
                "executed": False,
                "reason": "Entry order rejected",
                "entry_order_id": entry_order.get("id"),
            }

        if filled <= 0:
            return {
                "success": False,
                "executed": False,
                "reason": "Entry order not filled",
                "entry_order_id": entry_order.get("id"),
            }

        # 13. ارسال سفارش‌های محافظتی
        actual_entry = avg_price if avg_price is not None else entry
        actual_size = filled

        # بررسی هندسه با قیمت واقعی
        if direction == "LONG":
            if not (sl < actual_entry < tp):
                # وضعیت خطرناک؛ بستن فوری پوزیشن
                return self._emergency_close(symbol, "LONG", actual_size, "Invalid SL/TP after fill")
        else:
            if not (tp < actual_entry < sl):
                return self._emergency_close(symbol, "SHORT", actual_size, "Invalid SL/TP after fill")

        # ارسال SL reduce-only
        try:
            sl_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="stop_market",
                side="sell" if direction == "LONG" else "buy",
                amount=actual_size,
                params={"stopPrice": sl, "reduceOnly": True},
            )
        except Exception as e:
            # تلاش برای بستن اضطراری
            return self._emergency_close(symbol, direction, actual_size, f"SL order failed: {str(e)}")

        # ارسال TP reduce-only
        try:
            tp_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="take_profit_market",
                side="sell" if direction == "LONG" else "buy",
                amount=actual_size,
                params={"stopPrice": tp, "reduceOnly": True},
            )
        except Exception as e:
            # در صورت خطا، تلاش برای بستن اضطراری (SL ممکن است وجود داشته باشد)
            return self._emergency_close(symbol, direction, actual_size, f"TP order failed: {str(e)}")

        # 14. موفقیت
        return {
            "success": True,
            "executed": True,
            "symbol": symbol,
            "direction": direction,
            "entry_order_id": entry_order.get("id"),
            "stop_order_id": sl_order.get("id"),
            "take_profit_order_id": tp_order.get("id"),
            "requested_size": position_size,
            "filled_size": actual_size,
            "average_fill_price": actual_entry,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_amount": risk_amount,
            "status": "PROTECTED",
        }

    # ------------------------------------------------------------------
    # بستن اضطراری
    # ------------------------------------------------------------------
    def _emergency_close(self, symbol: str, direction: str, size: float, reason: str) -> Dict[str, Any]:
        """
        تلاش برای بستن اضطراری پوزیشن با سفارش reduce-only مخالف جهت.
        """
        opposite_side = "sell" if direction == "LONG" else "buy"
        try:
            close_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="market",
                side=opposite_side,
                amount=size,
                params={"reduceOnly": True},
            )
            return {
                "success": False,
                "executed": True,
                "protected": False,
                "emergency_action": "close",
                "reason": f"Emergency close: {reason}",
                "close_order_id": close_order.get("id"),
            }
        except Exception as e:
            # خطای بحرانی
            return {
                "success": False,
                "executed": True,
                "protected": False,
                "emergency_action": "failed",
                "reason": f"Emergency close failed: {reason}; {str(e)}",
            }
