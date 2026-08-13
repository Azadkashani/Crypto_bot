"""
آداپتور صرافی Gate.io برای بازار فیوچرز دائمی USDT-M.

این ماژول فقط خواندنی (Read-Only) است و هیچ‌گونه سفارش واقعی ارسال نمی‌کند.
حوزه مسئولیت:
    - اتصال به Gate.io futures
    - بارگذاری بازارها
    - اعتبارسنجی نمادهای USDT-M perpetual
    - فیلتر حداقل حجم ۲۴ ساعته USDT
    - دسترسی خواندنی به Ticker و OHLCV
    - دسترسی خواندنی به بالانس و پوزیشن‌ها (در صورت وجود دسترسی خصوصی)
    - جلوگیری از هرگونه عملیات نوشتن/سفارش

هشدار امنیتی:
    - هیچ API key یا secret چاپ یا بازگردانده نمی‌شود.
    - هیچ مسیر اجرای سفارش وجود ندارد.
"""

from __future__ import annotations

import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union

import config


MIN_24H_VOLUME_USDT = 1_000_000
SUPPORTED_TIMEFRAMES = {"5m", "1h", "4h"}


def _timeframe_to_timedelta(tf: str) -> timedelta:
    """تبدیل تایم‌فریم به timedelta."""
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    raise ValueError(f"Unsupported timeframe: {tf}")


class GateExchange:
    """
    آداپتور صرافی Gate.io با تأکید بر بازارهای USDT-M Perpetual.
    """

    def __init__(self, exchange_id: Optional[str] = None, options: Optional[dict] = None):
        """
        سازنده. آداپتور یک نمونه ccxt.gate می‌سازد و بازارها را بارگذاری می‌کند.

        پارامترها:
            exchange_id: شناسه صرافی. اگر None باشد از config.EXCHANGE_ID استفاده می‌شود.
            options: تنظیمات صرافی. اگر None باشد از config.EXCHANGE_OPTIONS استفاده می‌شود.
        """
        self.exchange_id = exchange_id or config.EXCHANGE_ID
        self.options = options or config.EXCHANGE_OPTIONS.copy()
        self.exchange = ccxt.gate(self.options)
        self.markets: Dict[str, Any] = {}
        # بارگذاری خودکار بازارها برای جلوگیری از KeyError در مصرف‌کنندگان
        try:
            self.load_markets()
        except Exception:
            # در صورت خطا، بازارها خالی می‌مانند؛ مصرف‌کننده باید خطای مناسب بدهد
            self.markets = {}

    # ------------------------------------------------------------------
    # بارگذاری بازار
    # ------------------------------------------------------------------
    def load_markets(self) -> Dict[str, Any]:
        """بارگذاری بازارها از صرافی و ذخیره در self.markets."""
        self.markets = self.exchange.load_markets()
        return self.markets

    # ------------------------------------------------------------------
    # دریافت بازار
    # ------------------------------------------------------------------
    def get_market(self, symbol: str) -> Dict[str, Any]:
        """دریافت اطلاعات بازار برای نماد مشخص."""
        if not self.markets:
            self.load_markets()
        market = self.markets.get(symbol)
        if market is None:
            raise ValueError(f"Symbol not found: {symbol}")
        return market

    # ------------------------------------------------------------------
    # اعتبارسنجی نماد USDT-M perpetual
    # ------------------------------------------------------------------
    def validate_perpetual_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        بررسی کامل بودن بازار به عنوان USDT-M perpetual.

        خروجی:
            دیکشنری با اطلاعات نرمال‌شده شامل:
                symbol, base, quote, settle, type, linear, swap, contract, spot

        در صورت عدم اعتبار، ValueError صادر می‌شود.
        """
        market = self.get_market(symbol)

        base = market.get("base")
        quote = market.get("quote")
        settle = market.get("settle")
        market_type = market.get("type") or market.get("swap") or market.get("contract")
        spot = market.get("spot", False)
        swap = market.get("swap", False)
        contract = market.get("contract", False)
        linear = market.get("linear", False)

        if spot:
            raise ValueError(f"Spot market is not allowed: {symbol}")

        if not contract and not swap:
            raise ValueError(f"Market is not a contract/swap: {symbol}")

        if not linear:
            raise ValueError(f"Market is not linear USDT-M: {symbol}")

        if str(settle).upper() != "USDT":
            raise ValueError(f"Market settlement is not USDT: {symbol}")

        if not base or not quote:
            raise ValueError(f"Market metadata missing base/quote: {symbol}")

        return {
            "symbol": symbol,
            "base": base,
            "quote": quote,
            "settle": settle,
            "type": market_type,
            "linear": linear,
            "swap": swap,
            "contract": contract,
            "spot": spot,
        }

    # ------------------------------------------------------------------
    # Ticker عمومی
    # ------------------------------------------------------------------
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        دریافت Ticker عمومی برای نماد.

        خروجی شامل:
            symbol, last, bid, ask, high, low, base_volume, quote_volume, timestamp
        """
        ticker = self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "last": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "base_volume": ticker.get("baseVolume") or ticker.get("base_volume"),
            "quote_volume": ticker.get("quoteVolume") or ticker.get("quote_volume"),
            "timestamp": ticker.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 500,
        closed_only: bool = False,
        current_time: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        دریافت داده OHLCV و تبدیل به DataFrame استاندارد.

        پارامترها:
            symbol: نماد معاملاتی.
            timeframe: تایم‌فریم مجاز (5m, 1h, 4h).
            limit: تعداد کندل.
            closed_only: اگر True باشد، آخرین کندل ناقص حذف می‌شود.
            current_time: زمان مرجع برای تشخیص کندل بسته‌شده.
                          اگر None باشد از زمان فعلی UTC استفاده می‌شود.

        خروجی:
            DataFrame با ستون‌های open, high, low, close, volume
            و ایندکس زمانی صعودی UTC.
        """
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        raw = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not raw:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        expected_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        if len(raw[0]) != len(expected_columns):
            raise ValueError("Missing OHLCV column")

        df = pd.DataFrame(raw, columns=expected_columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)

        if df.empty:
            return df
        if not df.index.is_monotonic_increasing:
            raise ValueError("OHLCV timestamps are not sorted ascending")
        if df.index.duplicated().any():
            raise ValueError("OHLCV timestamps contain duplicates")

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                raise ValueError(f"Missing OHLCV column: {col}")
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[["open", "high", "low", "close", "volume"]].isnull().any().any():
            raise ValueError("OHLCV contains non-numeric values")

        if closed_only:
            if current_time is None:
                current_time = pd.Timestamp.utcnow()
            else:
                current_time = pd.Timestamp(current_time)
            delta = _timeframe_to_timedelta(timeframe)
            closed_mask = df.index + delta <= current_time
            df = df.loc[closed_mask]

        return df

    # ------------------------------------------------------------------
    # حجم ۲۴ ساعته USDT
    # ------------------------------------------------------------------
    def get_24h_volume_usdt(self, symbol: str) -> Optional[float]:
        """
        دریافت حجم معاملات ۲۴ ساعته به USDT (quote volume).

        اگر حجم موجود نباشد یا نامعتبر باشد، None برمی‌گرداند.
        """
        try:
            ticker = self.get_ticker(symbol)
        except Exception:
            return None

        quote_volume = ticker.get("quote_volume")
        if quote_volume is None:
            return None
        try:
            volume = float(quote_volume)
        except (TypeError, ValueError):
            return None
        if volume != volume:  # NaN
            return None
        return volume

    # ------------------------------------------------------------------
    # بررسی واجد شرایط بودن بازار
    # ------------------------------------------------------------------
    def is_market_eligible(self, symbol: str) -> Dict[str, Any]:
        """
        بررسی واجد شرایط بودن بازار بر اساس نوع و حداقل حجم ۲۴ ساعته.

        خروجی:
            dict شامل:
                eligible: bool
                symbol: str
                volume_24h_usdt: float یا None
                reason: str
        """
        try:
            self.validate_perpetual_symbol(symbol)
        except ValueError as e:
            return {
                "eligible": False,
                "symbol": symbol,
                "volume_24h_usdt": None,
                "reason": str(e),
            }

        volume = self.get_24h_volume_usdt(symbol)

        if volume is None:
            return {
                "eligible": False,
                "symbol": symbol,
                "volume_24h_usdt": None,
                "reason": "24h USDT volume unavailable",
            }

        if volume < MIN_24H_VOLUME_USDT:
            return {
                "eligible": False,
                "symbol": symbol,
                "volume_24h_usdt": volume,
                "reason": "24h volume below minimum threshold",
            }

        return {
            "eligible": True,
            "symbol": symbol,
            "volume_24h_usdt": volume,
            "reason": "24h volume meets minimum threshold",
        }

    # ------------------------------------------------------------------
    # اسکن بازارهای واجد شرایط
    # ------------------------------------------------------------------
    def get_eligible_markets(self) -> List[Dict[str, Any]]:
        """
        بازگرداندن لیست بازارهای USDT-M perpetual با حجم ۲۴ ساعته >= 1M USDT.

        بازارهایی که حجم نامعتبر دارند یا نوع آن‌ها نادرست است حذف می‌شوند.
        """
        if not self.markets:
            self.load_markets()

        eligible = []
        for symbol in self.markets:
            result = self.is_market_eligible(symbol)
            if result["eligible"]:
                eligible.append(result)
        return eligible

    # ------------------------------------------------------------------
    # دسترسی خصوصی خواندنی
    # ------------------------------------------------------------------
    def _require_credentials(self):
        """بررسی وجود دسترسی خصوصی."""
        if not self.options.get("apiKey") or not self.options.get("secret"):
            raise PermissionError("Private data requires API credentials")

    def get_balance(self) -> Dict[str, Any]:
        """
        دریافت بالانس USDT (فقط خواندنی).

        خروجی:
            dict شامل currency, free, used, total
        """
        self._require_credentials()
        raw = self.exchange.fetch_balance()
        if "USDT" in raw:
            usdt = raw["USDT"]
        elif "total" in raw and "USDT" in raw.get("total", {}):
            usdt = {
                "free": raw.get("free", {}).get("USDT"),
                "used": raw.get("used", {}).get("USDT"),
                "total": raw.get("total", {}).get("USDT"),
            }
        else:
            usdt = {"free": None, "used": None, "total": None}
        return {
            "currency": "USDT",
            "free": usdt.get("free"),
            "used": usdt.get("used"),
            "total": usdt.get("total"),
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        دریافت پوزیشن‌های باز فیوچرز (فقط خواندنی).

        خروجی لیستی از dict شامل:
            symbol, side, contracts, entry_price, mark_price, unrealized_pnl, leverage
        """
        self._require_credentials()
        raw_positions = self.exchange.fetch_positions()
        positions = []
        for p in raw_positions:
            positions.append({
                "symbol": p.get("symbol"),
                "side": p.get("side"),
                "contracts": p.get("contracts"),
                "entry_price": p.get("entryPrice") or p.get("entry_price"),
                "mark_price": p.get("markPrice") or p.get("mark_price"),
                "unrealized_pnl": p.get("unrealizedPnl") or p.get("unrealized_pnl"),
                "leverage": p.get("leverage"),
            })
        return positions
