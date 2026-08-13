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
import decimal
from typing import Optional, Dict, Any

import config
from gate_exchange import GateExchange, MIN_24H_VOLUME_USDT


LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
if hasattr(config, "LIVE_TRADING_ENABLED"):
    LIVE_TRADING_ENABLED = bool(config.LIVE_TRADING_ENABLED)


class ExecutionEngine:
    """
    موتور اجرای واقعی سفارش با گیت‌های ایمنی چندلایه.
    """

    def __init__(self, exchange: GateExchange, live_trading_enabled: Optional[bool] = None):
        self.exchange = exchange
        self.live_trading_enabled = (
            LIVE_TRADING_ENABLED if live_trading_enabled is None else live_trading_enabled
        )
        self._duplicate_guard = set()

    # ------------------------------------------------------------------
    # گیت‌ها
    # ------------------------------------------------------------------
    def _is_live_enabled(self) -> bool:
        return self.live_trading_enabled

    def _validate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(signal, dict):
            return {"valid": False, "reason": "Signal must be a dictionary"}
        if signal.get("valid") is not True:
            return {"valid": False, "reason": "Signal is not valid"}
        direction = signal.get("signal")
        if direction not in ("LONG", "SHORT"):
            return {"valid": False, "reason": "Invalid signal direction"}
        return {"valid": True, "direction": direction}

    def _validate_prices(self, direction: str, entry: float, sl: float, tp: float) -> Dict[str, Any]:
        if not all(isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)
                   for x in (entry, sl, tp)):
            return {"valid": False, "reason": "Invalid price values"}
        if entry <= 0 or sl <= 0 or tp <= 0:
            return {"valid": False, "reason": "Prices must be positive"}
        if direction == "LONG":
            if not (sl < entry < tp):
                return {"valid": False, "reason": "LONG price relationship invalid"}
        else:
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
        if risk > expected_risk * 1.001:
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
        try:
            result = self.exchange.is_market_eligible(symbol)
            if not result.get("eligible"):
                return {"valid": False, "reason": result.get("reason", "Market not eligible")}
            return {"valid": True, "volume": result.get("volume_24h_usdt")}
        except Exception as e:
            return {"valid": False, "reason": f"Market eligibility check failed: {str(e)}"}

    def _check_balance(self, risk_amount: float) -> Dict[str, Any]:
        try:
            balance = self.exchange.get_balance()
            if not isinstance(balance, dict):
                return {"valid": False, "reason": "Balance unavailable"}
            total = balance.get("total")
            if total is None or total <= 0:
                return {"valid": False, "reason": "Balance unavailable"}
            if total < risk_amount:
                return {"valid": False, "reason": "Insufficient balance"}
            return {"valid": True, "balance": float(total)}
        except PermissionError:
            return {"valid": False, "reason": "Balance unavailable"}
        except Exception as e:
            return {"valid": False, "reason": f"Balance check failed: {str(e)}"}

    def _check_existing_positions(self, symbol: str) -> Dict[str, Any]:
        try:
            positions = self.exchange.get_positions()
            if isinstance(positions, list):
                for pos in positions:
                    if pos.get("symbol") == symbol and pos.get("contracts") not in (0, None):
                        return {"valid": False, "reason": "Existing position"}
                return {"valid": True}
            return {"valid": False, "reason": "Position data unavailable"}
        except PermissionError:
            return {"valid": False, "reason": "Position data unavailable"}
        except Exception as e:
            return {"valid": False, "reason": f"Position check failed: {str(e)}"}

    def _check_quantity_precision(self, symbol: str, quantity: float) -> Dict[str, Any]:
        try:
            market = self.exchange.get_market(symbol)
            precision = market.get("precision", {}).get("amount")
            limits = market.get("limits", {})
            min_amount = limits.get("amount", {}).get("min")
            min_cost = limits.get("cost", {}).get("min")

            if precision is None:
                return {"valid": False, "reason": "No amount precision information"}

            import decimal
            d = decimal.Decimal(str(quantity))
            step = decimal.Decimal(str(precision))
            rounded = float(d.quantize(step, rounding=decimal.ROUND_DOWN))
            if rounded <= 0:
                return {"valid": False, "reason": "Quantity rounded to zero"}
            if min_amount is not None and rounded < min_amount:
                return {"valid": False, "reason": "Quantity below minimum"}
            if min_cost is not None:
                ticker = self.exchange.get_ticker(symbol)
                last = ticker.get("last")
                if last is not None and rounded * last < min_cost:
                    return {"valid": False, "reason": "Notional below minimum"}
            return {"valid": True, "rounded_quantity": rounded}
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
        # GATE 0: Live trading
        if not self._is_live_enabled():
            return {
                "success": False,
                "executed": False,
                "reason": "Live trading disabled",
            }

        # GATE 1: Signal validity
        signal_check = self._validate_signal(signal)
        if not signal_check["valid"]:
            return {"success": False, "executed": False, "reason": signal_check["reason"]}
        direction = signal_check["direction"]

        # GATE 2: Symbol/market validation
        symbol = signal.get("symbol") or config.SYMBOL
        try:
            self.exchange.validate_perpetual_symbol(symbol)
        except ValueError as e:
            return {"success": False, "executed": False, "reason": str(e)}

        # GATE 3: 24h volume eligibility
        market_check = self._check_market_eligibility(symbol)
        if not market_check["valid"]:
            return {"success": False, "executed": False, "reason": market_check["reason"]}

        # قیمت‌ها
        entry = signal.get("entry_price")
        sl = signal.get("stop_loss")
        tp = signal.get("take_profit")
        price_check = self._validate_prices(direction, entry, sl, tp)
        if not price_check["valid"]:
            return {"success": False, "executed": False, "reason": price_check["reason"]}

        position_size = signal.get("position_size")
        size_check = self._validate_position_size(position_size)
        if not size_check["valid"]:
            return {"success": False, "executed": False, "reason": size_check["reason"]}

        risk_amount = signal.get("risk_amount")
        if risk_amount is None:
            return {"success": False, "executed": False, "reason": "Missing risk amount"}

        leverage = signal.get("leverage", config.LEVERAGE)
        lev_check = self._validate_leverage(leverage)
        if not lev_check["valid"]:
            return {"success": False, "executed": False, "reason": lev_check["reason"]}

        # GATE 5: بالانس
        balance_check = self._check_balance(risk_amount)
        if not balance_check["valid"]:
            return {"success": False, "executed": False, "reason": balance_check["reason"]}

        # GATE 6: پوزیشن‌های موجود
        position_check = self._check_existing_positions(symbol)
        if not position_check["valid"]:
            return {"success": False, "executed": False, "reason": position_check["reason"]}

        # GATE 8: Risk validation
        expected_risk = balance_check["balance"] * config.RISK_PER_TRADE
        risk_check = self._validate_risk_amount(risk_amount, expected_risk)
        if not risk_check["valid"]:
            return {"success": False, "executed": False, "reason": risk_check["reason"]}

        # GATE 10: Quantity precision
        precision_result = self._check_quantity_precision(symbol, position_size)
        if not precision_result["valid"]:
            return {"success": False, "executed": False, "reason": precision_result["reason"]}
        rounded_quantity = precision_result.get("rounded_quantity", position_size)

        # Duplicate guard
        signal_hash = f"{symbol}:{direction}:{entry}:{sl}:{tp}:{rounded_quantity}"
        duplicate_check = self._check_duplicate_order(signal_hash)
        if not duplicate_check["valid"]:
            return {"success": False, "executed": False, "reason": duplicate_check["reason"]}
        self._duplicate_guard.add(signal_hash)

        # GATE 13: Final market eligibility re-check
        final_market_check = self._check_market_eligibility(symbol)
        if not final_market_check["valid"]:
            self._duplicate_guard.discard(signal_hash)
            return {"success": False, "executed": False, "reason": final_market_check["reason"]}

        # GATE 14: Final balance re-check
        final_balance_check = self._check_balance(risk_amount)
        if not final_balance_check["valid"]:
            self._duplicate_guard.discard(signal_hash)
            return {"success": False, "executed": False, "reason": final_balance_check["reason"]}

        # GATE 15: Final position re-check
        final_position_check = self._check_existing_positions(symbol)
        if not final_position_check["valid"]:
            self._duplicate_guard.discard(signal_hash)
            return {"success": False, "executed": False, "reason": final_position_check["reason"]}

        # GATE 16: Submit entry order
        order_side = "buy" if direction == "LONG" else "sell"
        try:
            entry_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="market",
                side=order_side,
                amount=rounded_quantity,
                params={"reduceOnly": False},
            )
        except Exception as e:
            # Ambiguous network error: check exchange state
            self._duplicate_guard.discard(signal_hash)
            self._check_existing_positions(symbol)
            return {
                "success": False,
                "executed": False,
                "reason": f"Entry order failed: {str(e)}",
            }

        # GATE 17: Verify entry result
        try:
            order_info = self.exchange.exchange.fetch_order(entry_order["id"], symbol)
            status = order_info.get("status")
            filled = order_info.get("filled", 0)
            avg_price = order_info.get("average") or order_info.get("price")
        except Exception:
            self._duplicate_guard.discard(signal_hash)
            return {
                "success": False,
                "executed": False,
                "reason": "Entry order verification failed",
                "entry_order_id": entry_order.get("id"),
            }

        if status == "rejected":
            return {
                "success": False,
                "executed": False,
                "reason": "Entry order rejected",
                "entry_order_id": entry_order.get("id"),
            }

        if status in ("canceled", "cancelled") or filled <= 0:
            return {
                "success": False,
                "executed": False,
                "reason": "Entry order not filled",
                "entry_order_id": entry_order.get("id"),
            }

        actual_entry = avg_price if avg_price is not None else entry
        actual_size = filled

        # Validate SL/TP against actual price
        if direction == "LONG":
            if not (sl < actual_entry < tp):
                return self._emergency_close(symbol, direction, actual_size, "Invalid SL/TP after fill")
        else:
            if not (tp < actual_entry < sl):
                return self._emergency_close(symbol, direction, actual_size, "Invalid SL/TP after fill")

        # GATE 18: Create SL
        try:
            sl_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="stop_market",
                side="sell" if direction == "LONG" else "buy",
                amount=actual_size,
                params={"stopPrice": sl, "reduceOnly": True},
            )
        except Exception as e:
            return self._emergency_close(symbol, direction, actual_size, f"SL order failed: {str(e)}")

        # GATE 19: Create TP
        try:
            tp_order = self.exchange.exchange.create_order(
                symbol=symbol,
                type="take_profit_market",
                side="sell" if direction == "LONG" else "buy",
                amount=actual_size,
                params={"stopPrice": tp, "reduceOnly": True},
            )
        except Exception as e:
            return self._emergency_close(symbol, direction, actual_size, f"TP order failed: {str(e)}")

        # Success
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
            return {
                "success": False,
                "executed": True,
                "protected": False,
                "emergency_action": "failed",
                "reason": f"Emergency close failed: {reason}; {str(e)}",
            }
