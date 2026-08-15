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
from position_sizing import calculate_position_size


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
    # همگام‌سازی زمانی
    # ------------------------------------------------------------------
    def _get_latest_decision_time(self) -> pd.Timestamp:
        """
        یافتن آخرین زمان بسته‌شدن کندل 5m از داده واقعی.
        اگر داده‌ای موجود نبود، از زمان فعلی استفاده می‌شود.
        """
        for sym in self.symbols:
            try:
                df = self.exchange.get_ohlcv(
                    sym, config.TIMEFRAME_5M, limit=2, closed_only=False
                )
                if not df.empty:
                    last_start = df.index[-1]
                    # زمان بسته‌شدن آخرین کندل
                    return last_start + pd.Timedelta(minutes=5)
            except Exception:
                continue
        return pd.Timestamp.now(tz='UTC')

    # ------------------------------------------------------------------
    # اجرای زنده
    # ------------------------------------------------------------------
    def run_once(self, current_time: Optional[pd.Timestamp] = None) -> None:
        """یک سیکل کامل از Receive → Analysis → Signal → Paper → Monitor."""
        if not config.PAPER_TRADING:
            logger.critical("PAPER_TRADING=False detected! Exiting to avoid real orders.")
            return

        # همگام‌سازی زمانی: استفاده از آخرین کندل بسته‌شده 5m
        decision_time = self._get_latest_decision_time()
        logger.info("=" * 70)
        logger.info(f"PAPER TRADING MODE - REAL ORDERS DISABLED | Decision Time: {decision_time}")
        logger.info("=" * 70)

        # 1) Monitor existing paper positions
        self._monitor_open_positions(decision_time)

        # 2) جمع‌آوری کاندیداها
        candidates: List[Dict[str, Any]] = []

        for sym in self.symbols:
            # جلوگیری از سیگنال تکراری در همان decision_time
            if sym in self.last_signal_timestamps:
                last_ts = self.last_signal_timestamps[sym]
                if last_ts == decision_time:
                    continue

            try:
                signal = self._generate_signal_for_symbol(sym, decision_time)
            except Exception as e:
                logger.warning(f"خطا در تحلیل {sym}: {e}")
                continue

            if signal is None:
                continue

            # دریافت قیمت لحظه‌ای و اعتبارسنجی فاصله قیمت
            try:
                ticker = self.exchange.get_ticker(sym)
                live_price = float(ticker.get('last', 0))
                volume_24h = float(ticker.get('quote_volume', 0))
            except Exception as e:
                logger.warning(f"دریافت Ticker برای {sym} ناموفق: {e}")
                continue

            if live_price <= 0:
                logger.warning(f"Live price invalid for {sym}")
                continue

            if volume_24h < 1_000_000:
                logger.info(f"{sym} حجم ۲۴ ساعته کمتر از ۱٬۰۰۰٬۰۰۰ - نادیده گرفته می‌شود")
                continue

            # بررسی انحراف قیمت
            entry_price = signal.get("entry_price")
            if entry_price is None:
                continue

            deviation = abs(live_price - entry_price) / entry_price
            if deviation > config.MAX_ENTRY_PRICE_DEVIATION:
                logger.warning(
                    f"{sym} قیمت لحظه‌ای {live_price:.2f} با Entry سیگنال {entry_price:.2f} "
                    f"اختلاف {deviation:.4f} دارد - سیگنال رد شد"
                )
                continue

            # شرط‌های LONG/SHORT با قیمت لحظه‌ای
            take_profit = signal.get("take_profit")
            if signal["signal"] == "LONG":
                if live_price > take_profit or live_price > entry_price * (1 + config.MAX_ENTRY_PRICE_DEVIATION):
                    logger.warning(f"{sym} LONG با قیمت لحظه‌ای {live_price:.2f} معتبر نیست - سیگنال رد شد")
                    continue
            else:  # SHORT
                if live_price < take_profit or live_price < entry_price * (1 - config.MAX_ENTRY_PRICE_DEVIATION):
                    logger.warning(f"{sym} SHORT با قیمت لحظه‌ای {live_price:.2f} معتبر نیست - سیگنال رد شد")
                    continue

            # اضافه کردن قیمت لحظه‌ای به سیگنال
            signal["live_price"] = live_price
            signal["volume_24h_usdt"] = volume_24h

            candidate = {**signal, "symbol": sym}

            score = signal_scoring.calculate_score(candidate)
            if score is None:
                continue
            candidate["score"] = score
            candidates.append(candidate)
            self.last_signal_timestamps[sym] = decision_time

            logger.info(
                f"[SCAN] {sym} Direction={candidate.get('signal')} Score={score:.2f} "
                f"Entry={candidate.get('entry_price'):.2f} Live={live_price:.2f} "
                f"SL={candidate.get('stop_loss'):.2f} TP={candidate.get('take_profit'):.2f}"
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
            self._open_paper_position(best, decision_time)

    def _generate_signal_for_symbol(self, symbol: str, decision_time: pd.Timestamp) -> Optional[Dict[str, Any]]:
        """دریافت داده و تولید سیگنال با Strategy فعلی."""
        try:
            df_4h = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_4H, limit=500, closed_only=True, current_time=decision_time
            )
            df_1h = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_1H, limit=500, closed_only=True, current_time=decision_time
            )
            df_5m = self.exchange.get_ohlcv(
                symbol, config.TIMEFRAME_5M, limit=500, closed_only=True, current_time=decision_time
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
            as_of=decision_time,
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

    def _open_paper_position(self, signal: Dict[str, Any], decision_time: pd.Timestamp) -> None:
        """ایجاد Paper Position از یک سیگنال معتبر با قیمت ورود لحظه‌ای."""
        symbol = signal["symbol"]
        if symbol in self.open_positions:
            logger.warning(f"سیگنال تکراری برای {symbol} نادیده گرفته می‌شود")
            return

        if len(self.open_positions) >= config.MAX_CONCURRENT_POSITIONS:
            logger.warning("حداکثر تعداد پوزیشن‌های همزمان رسیده است")
            return

        # دریافت قیمت لحظه‌ای
        try:
            ticker = self.exchange.get_ticker(symbol)
            live_price = float(ticker.get('last', 0))
        except Exception as e:
            logger.warning(f"خطا در دریافت Live Price برای {symbol}: {e}")
            return

        if live_price <= 0:
            logger.warning(f"Live Price نامعتبر برای {symbol}")
            return

        # بررسی دوباره انحراف
        entry_signal = signal.get("entry_price")
        deviation = abs(live_price - entry_signal) / entry_signal
        if deviation > config.MAX_ENTRY_PRICE_DEVIATION:
            logger.warning(f"اختلاف قیمت ورود برای {symbol} از حد مجاز عبور کرد - سیگنال رد شد")
            return

        # محاسبه Position Sizing با قیمت لحظه‌ای
        pos = calculate_position_size(
            account_balance=self.current_balance,
            risk_per_trade=config.RISK_PER_TRADE,
            entry_price=live_price,
            stop_loss=signal["stop_loss"],
            allocation=config.POSITION_ALLOCATION,
            max_leverage=config.MAX_LEVERAGE,
        )
        if not pos["valid"]:
            logger.warning(f"Position Sizing برای {symbol} نامعتبر: {pos.get('reason')}")
            return

        position = {
            "symbol": symbol,
            "direction": signal["signal"],
            "entry_time": decision_time,
            "entry_price": live_price,               # ورود با قیمت لحظه‌ای
            "stop_loss": float(signal["stop_loss"]),
            "take_profit": float(signal["take_profit"]),
            "position_size": float(pos["position_size"]),
            "risk_amount": float(pos["risk_amount"]),
            "leverage": float(pos["leverage"]),
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
            f"Lev={position['leverage']:.2f} Live={live_price:.2f}"
        )

    def _monitor_open_positions(self, decision_time: pd.Timestamp) -> None:
        """بررسی SL/TP برای پوزیشن‌های باز."""
        for sym in list(self.open_positions.keys()):
            position = self.open_positions[sym]
            try:
                df_5m = self.exchange.get_ohlcv(
                    sym, config.TIMEFRAME_5M, limit=5, closed_only=True, current_time=decision_time
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

            self._close_paper_position(sym, exit_price, exit_reason, decision_time)

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
