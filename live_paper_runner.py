"""
Live Market Connection + Signal-Only Paper Trading.

این ماژول:
    - به Gate.io Futures متصل می‌شود.
    - فقط Symbolهای موجود در Whitelist را تحلیل می‌کند.
    - داده 4h/1h/5m واقعی دریافت می‌کند.
    - Strategy فعلی را اجرا می‌کند.
    - Score/Ranking انجام می‌دهد.
    - Paper Position می‌سازد و SL/TP را monitor می‌کند.
    - هیچ سفارش واقعی ارسال نمی‌کند.

PAPER_TRADING = True در config اجباری است.
"""

from __future__ import annotations

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import timezone, timedelta

import config
from gate_exchange import GateExchange
from historical_data import validate_ohlcv
import strategy
import signal_scoring


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class LivePaperTradingRunner:
    """
    اجرای ربات به صورت Live Signal / Paper Trading.
    """

    def __init__(self, exchange: GateExchange, symbols: Optional[List[str]] = None):
        self.exchange = exchange
        self.symbols = symbols if symbols is not None else config.SYMBOL_WHITELIST
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.last_signal_timestamps: Dict[str, pd.Timestamp] = {}
        self.current_balance = float(config.ACCOUNT_BALANCE)

    # ------------------------------------------------------------------
    # اجرای زنده
    # ------------------------------------------------------------------
    def run_once(self, current_time: Optional[pd.Timestamp] = None) -> None:
        """یک سیکل کامل از Receive → Analysis → Signal → Paper → Monitor."""
        if not config.PAPER_TRADING:
            logger.critical("PAPER_TRADING=False detected! Exiting to avoid real orders.")
            return

        if current_time is None:
            current_time = pd.Timestamp.now(tz='UTC')

        logger.info("=" * 70)
        logger.info("PAPER TRADING MODE - REAL ORDERS DISABLED")
        logger.info("=" * 70)

        # 1) Monitor existing paper positions
        self._monitor_open_positions(current_time)

        # 2) جمع‌آوری کاندیداها
        candidates: List[Dict[str, Any]] = []

        for sym in self.symbols:
            # تکراری نشدن سیگنال در یک کندل
            if sym in self.last_signal_timestamps:
                last_ts = self.last_signal_timestamps[sym]
                # برای سادگی فقط مانع در همان ثانیه
                if last_ts == current_time:
                    continue

            try:
                signal = self._generate_signal_for_symbol(sym, current_time)
            except Exception as e:
                logger.warning(f"خطا در تحلیل {sym}: {e}")
                continue

            if signal is None:
                continue

            # اضافه کردن حجم ۲۴ ساعته
            try:
                ticker = self.exchange.get_ticker(sym)
                volume_24h = float(ticker.get('quote_volume', 0))
            except Exception:
                volume_24h = 0.0

            if volume_24h < 1_000_000:
                logger.info(f"{sym} حجم ۲۴ ساعته کمتر از ۱٬۰۰۰٬۰۰۰ - نادیده گرفته می‌شود")
                continue

            candidate = {**signal, "symbol": sym, "volume_24h_usdt": volume_24h}

            score = signal_scoring.calculate_score(candidate)
            if score is None:
                continue
            candidate["score"] = score
            candidates.append(candidate)
            self.last_signal_timestamps[sym] = current_time

            logger.info(
                f"[SCAN] {sym} Direction={candidate.get('signal')} Score={score:.2f} "
                f"Entry={candidate.get('entry_price'):.2f} SL={candidate.get('stop_loss'):.2f}"
            )

        if not candidates:
            logger.info("هیچ سیگنال معتبری در این سیکل یافت نشد.")
            return

        # 3) Ranking و انتخاب بهترین‌ها با سقف 4 پوزیشن
        candidates = self._filter_open_symbols(candidates)
        if not candidates:
            logger.info("همه کاندیداها Symbol باز دارند.")
            return

        # حذف تکراری هر Symbol (بهترین Score)
        best_per_symbol: Dict[str, Dict[str, Any]] = {}
        for c in candidates:
            sym = c["symbol"]
            if sym not in best_per_symbol or c["score"] > best_per_symbol[sym]["score"]:
                best_per_symbol[sym] = c
        candidates = list(best_per_symbol.values())

        ranked = signal_scoring.rank_signals(candidates)
        slots = config.MAX_CONCURRENT_POSITIONS - len(self.open_positions)
        selected = ranked[:slots]

        for best in selected:
            self._open_paper_position(best, current_time)

    def _generate_signal_for_symbol(self, symbol: str, current_time: pd.Timestamp) -> Optional[Dict[str, Any]]:
        """دریافت داده و تولید سیگنال با Strategy فعلی."""
        try:
            df_4h = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_4H, limit=500, closed_only=True, current_time=current_time
            )
            df_1h = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_1H, limit=500, closed_only=True, current_time=current_time
            )
            df_5m = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_5M, limit=500, closed_only=True, current_time=current_time
            )
        except Exception as e:
            logger.warning(f"دریافت داده ناموفق برای {symbol}: {e}")
            return None

        if df_5m.empty:
            return None

        signal = strategy.generate_signal(
            df_4h,
            df_1h,
            df_5m,
            as_of=current_time,
            account_balance=self.current_balance,
            symbol=symbol,
        )

        if signal.get("valid") is not True or signal.get("signal") not in ("LONG", "SHORT"):
            return None

        return signal

    # ------------------------------------------------------------------
    # مدیریت Paper Positions
    # ------------------------------------------------------------------
    def _filter_open_symbols(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [c for c in candidates if c["symbol"] not in self.open_positions]

    def _open_paper_position(self, signal: Dict[str, Any], current_time: pd.Timestamp) -> None:
        """ایجاد Paper Position از یک سیگنال معتبر."""
        symbol = signal["symbol"]
        if symbol in self.open_positions:
            logger.warning(f"سیگنال تکراری برای {symbol} نادیده گرفته می‌شود")
            return

        if len(self.open_positions) >= config.MAX_CONCURRENT_POSITIONS:
            logger.warning("حداکثر تعداد پوزیشن‌های همزمان رسیده است")
            return

        position = {
            "symbol": symbol,
            "direction": signal["signal"],
            "entry_time": current_time,
            "entry_price": float(signal["entry_price"]),
            "stop_loss": float(signal["stop_loss"]),
            "take_profit": float(signal["take_profit"]),
            "position_size": float(signal["position_size"]),
            "risk_amount": float(signal["risk_amount"]),
            "leverage": float(signal.get("leverage", 0.0)),
            "score": signal.get("score"),
            "r_multiple": 0.0,
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "pnl": 0.0,
        }

        self.open_positions[symbol] = position

        logger.info(
            f"[PAPER SIGNAL] {symbol} {position['direction']} Score={position['score']:.2f} "
            f"Entry={position['entry_price']:.2f} SL={position['stop_loss']:.2f} "
            f"TP={position['take_profit']:.2f} Risk={position['risk_amount']:.2f} "
            f"Lev={position['leverage']:.2f}"
        )

    def _monitor_open_positions(self, current_time: pd.Timestamp) -> None:
        """بررسی SL/TP برای پوزیشن‌های باز."""
        for sym in list(self.open_positions.keys()):
            position = self.open_positions[sym]
            try:
                df_5m = self.exchange.get_ohlcv(
                    sym, config.TIMEFRAME_5M, limit=5, closed_only=True, current_time=current_time
                )
                if df_5m.empty:
                    continue
                candle = df_5m.iloc[-1]
            except Exception as e:
                logger.warning(f"خطا در مانیتور {sym}: {e}")
                continue

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
                    continue
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
                    continue

            self._close_paper_position(sym, exit_price, exit_reason, current_time)

    def _close_paper_position(self, symbol: str, exit_price: float, exit_reason: str, exit_time: pd.Timestamp) -> None:
        """بستن Paper Position و ثبت معامله."""
        position = self.open_positions.pop(symbol, None)
        if position is None:
            return

        direction = position["direction"]
        entry = position["entry_price"]
        size = position["position_size"]
        risk = position["risk_amount"]

        if direction == "LONG":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        r_multiple = pnl / risk if risk else 0.0
        self.current_balance += pnl

        position.update({
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "r_multiple": r_multiple,
            "balance_after": self.current_balance,
        })

        self.closed_trades.append(position)

        logger.info(
            f"[PAPER EXIT] {symbol} Exit={exit_price:.2f} Reason={exit_reason} "
            f"PnL={pnl:.2f} R={r_multiple:.2f} Balance={self.current_balance:.2f}"
        )

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        return self.open_positions

    def get_closed_trades(self) -> List[Dict[str, Any]]:
        return self.closed_trades

    def run_loop(self, interval_seconds: int = 300):
        """اجرای مداوم با فاصله مشخص."""
        logger.info("شروع حلقه Live Paper Trading")
        while config.PAPER_TRADING:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"خطای غیرمنتظره: {e}")
            time.sleep(interval_seconds)


def main():
    """نقطه ورود برای اجرای Live Paper Trading."""
    exchange = GateExchange()
    exchange.load_markets()

    runner = LivePaperTradingRunner(exchange, config.SYMBOL_WHITELIST)
    runner.run_loop(interval_seconds=300)


if __name__ == "__main__":
    main()
