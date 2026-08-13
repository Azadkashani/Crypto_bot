"""
Orchestrator چندنمادی و Safety Layer نهایی.

این ماژول وظیفه دارد:
    - چند Symbol را بررسی کند.
    - سیگنال‌های معتبر را جمع‌آوری کند.
    - از scoring و ranking موجود فاز ۱۶ استفاده کند.
    - یک Safety Gate نهایی قبل از ExecutionEngine اعمال کند.
    - فقط بهترین سیگنال را برای اجرا ارسال کند.

هیچ سفارشی در این ماژول ارسال نمی‌شود مگر از طریق ExecutionEngine موجود.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import pandas as pd

import config
import strategy
import signal_scoring


class MultiSymbolOrchestrator:
    """
    ارکستراتور چندنمادی برای جمع‌آوری، امتیازدهی و انتخاب بهترین سیگنال.
    """

    def __init__(
        self,
        exchange,
        execution_engine=None,
        live_trading_enabled: bool = False,
    ):
        """
        پارامترها:
            exchange: آداپتور GateExchange که داده‌های بازار را فراهم می‌کند.
            execution_engine: (اختیاری) ExecutionEngine فاز ۱۵ برای اجرای واقعی.
            live_trading_enabled: اگر False باشد، هیچ سفارشی ارسال نمی‌شود.
        """
        self.exchange = exchange
        self.execution_engine = execution_engine
        self.live_trading_enabled = live_trading_enabled
        self._executed_hashes = set()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _is_market_eligible(self, symbol: str) -> Dict[str, Any]:
        """بررسی بازار با GateExchange."""
        return self.exchange.is_market_eligible(symbol)

    def _get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        as_of: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """دریافت داده OHLCV بسته‌شده."""
        return self.exchange.get_ohlcv(
            symbol,
            timeframe,
            limit=500,
            closed_only=True,
            current_time=as_of,
        )

    def _process_symbol(
        self,
        symbol: str,
        as_of: Optional[pd.Timestamp] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        بررسی کامل یک Symbol:
            Market eligibility → Data → Strategy → Scoring
        """
        # 1) Market eligibility + Volume filter
        eligibility = self._is_market_eligible(symbol)
        if not eligibility.get("eligible"):
            return None

        volume = eligibility.get("volume_24h_usdt")
        if volume is None:
            return None

        try:
            df_4h = self._get_ohlcv(symbol, config.TIMEFRAME_4H, as_of)
            df_1h = self._get_ohlcv(symbol, config.TIMEFRAME_1H, as_of)
            df_5m = self._get_ohlcv(symbol, config.TIMEFRAME_5M, as_of)
        except Exception:
            # خطای داده یک Symbol نباید کل اسکن را متوقف کند
            return None

        signal = strategy.generate_signal(
            df_4h,
            df_1h,
            df_5m,
            as_of=as_of,
            account_balance=config.ACCOUNT_BALANCE,
        )

        if signal.get("valid") is not True:
            return None
        if signal.get("signal") not in ("LONG", "SHORT"):
            return None

        candidate = {**signal, "symbol": symbol, "volume_24h_usdt": volume}

        score = signal_scoring.calculate_score(candidate)
        if score is None:
            return None

        candidate["score"] = score
        return candidate

    def _safety_recheck(self, best: Dict[str, Any]) -> tuple[bool, str]:
        """Safety Gate نهایی قبل از ارسال سفارش."""
        symbol = best.get("symbol")

        # Market recheck
        eligibility = self._is_market_eligible(symbol)
        if not eligibility.get("eligible"):
            return False, "Market eligibility failed"
        volume = eligibility.get("volume_24h_usdt", 0)
        if volume is None or volume < signal_scoring.MIN_24H_VOLUME_USDT:
            return False, "Volume below minimum threshold"

        # Balance recheck
        try:
            balance = self.exchange.get_balance()
            total = balance.get("total")
            if total is None or total < best.get("risk_amount", 0):
                return False, "Insufficient balance"
        except PermissionError:
            return False, "Balance unavailable"
        except Exception as e:
            return False, f"Balance check failed: {e}"

        # Position recheck
        try:
            positions = self.exchange.get_positions()
            for pos in positions:
                if pos.get("symbol") == symbol and pos.get("contracts") not in (0, None):
                    return False, "Existing position"
        except Exception as e:
            return False, f"Position check failed: {e}"

        # Risk recheck
        entry = best.get("entry_price")
        sl = best.get("stop_loss")
        tp = best.get("take_profit")
        size = best.get("position_size")
        risk = best.get("risk_amount")

        try:
            entry = float(entry)
            sl = float(sl)
            tp = float(tp)
            size = float(size)
            risk = float(risk)
        except (TypeError, ValueError):
            return False, "Invalid risk parameters"

        if not all(x > 0 for x in (entry, sl, tp, size, risk)):
            return False, "Invalid risk parameters"

        if best["signal"] == "LONG":
            if not (sl < entry < tp):
                return False, "Invalid LONG price geometry"
        else:
            if not (tp < entry < sl):
                return False, "Invalid SHORT price geometry"

        # Duplicate protection
        signal_hash = f"{symbol}:{best['signal']}:{entry}:{sl}:{tp}:{size}"
        if signal_hash in self._executed_hashes:
            return False, "Duplicate order detected"

        return True, signal_hash

    # ------------------------------------------------------------------
    # اجرای اصلی
    # ------------------------------------------------------------------
    def run(
        self,
        symbols: List[str],
        as_of: Optional[pd.Timestamp] = None,
    ) -> Dict[str, Any]:
        """
        اسکن چند Symbol، انتخاب بهترین سیگنال و اجرای امن آن.

        خروجی:
            dict شامل success, signal, symbol, score, reason, candidates_count, candidates
        """
        candidates: List[Dict[str, Any]] = []

        for symbol in symbols:
            try:
                candidate = self._process_symbol(symbol, as_of)
                if candidate is not None:
                    candidates.append(candidate)
            except Exception:
                # خطای یک Symbol نباید کل اسکن را متوقف کند
                continue

        if not candidates:
            return {
                "success": False,
                "signal": "NONE",
                "symbol": None,
                "score": None,
                "reason": "No valid signals",
                "candidates_count": 0,
                "candidates": [],
            }

        ranked = signal_scoring.rank_signals(candidates)
        best = ranked[0]

        # Live trading gate
        if not self.live_trading_enabled:
            return {
                "success": False,
                "signal": "NONE",
                "symbol": best.get("symbol"),
                "score": best.get("score"),
                "reason": "Live trading disabled",
                "candidates_count": len(candidates),
                "candidates": ranked,
            }

        # Final safety recheck
        safety_ok, safety_value = self._safety_recheck(best)
        if not safety_ok:
            return {
                "success": False,
                "signal": "NONE",
                "symbol": best.get("symbol"),
                "score": best.get("score"),
                "reason": safety_value,
                "candidates_count": len(candidates),
                "candidates": ranked,
            }

        # Duplicate guard قبل از اجرا
        self._executed_hashes.add(safety_value)

        if self.execution_engine is not None:
            execution_result = self.execution_engine.execute(best)
        else:
            execution_result = {"success": True, "executed": True}

        if execution_result.get("success"):
            return {
                "success": True,
                "signal": best.get("signal"),
                "symbol": best.get("symbol"),
                "score": best.get("score"),
                "reason": "Executed",
                "candidates_count": len(candidates),
                "candidates": ranked,
                "execution": execution_result,
            }

        return {
            "success": False,
            "signal": "NONE",
            "symbol": best.get("symbol"),
            "score": best.get("score"),
            "reason": execution_result.get("reason", "Execution failed"),
            "candidates_count": len(candidates),
            "candidates": ranked,
            "execution": execution_result,
        }
