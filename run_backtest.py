#!/usr/bin/env python3
"""
اجرای Backtest واقعی روی داده‌های تاریخی Gate.io Futures.

این اسکریپت:
    - لیست Symbol های واجد شرایط را از Market Scanner می‌گیرد
    - داده‌های 4h ،1h و 5m را دریافت یا از CSV می‌خواند
    - بک‌تست چندنمادی را با استفاده از HistoricalBacktestRunner اجرا می‌کند
    - گزارش عملکرد را چاپ می‌کند

توجه:
    - این اسکریپت هیچ سفارش واقعی ارسال نمی‌کند.
    - برای حجم ۲۴ ساعته تاریخی، اگر داده‌ی دقیق موجود نباشد، از حجم فعلی
      استفاده می‌شود که ممکن است Bias ایجاد کند؛ برای بک‌تست دقیق باید
      منبع حجم تاریخی فراهم شود.
"""

import os
import pandas as pd
from datetime import datetime, timezone

from gate_exchange import GateExchange
from historical_backtest import HistoricalBacktestRunner, HistoricalDataProvider
import config


# ----------------------------------------------------------------------
# تنظیمات بک‌تست
# ----------------------------------------------------------------------
BACKTEST_START = "2025-01-01T00:00:00+00:00"
BACKTEST_END = "2025-02-01T00:00:00+00:00"

INITIAL_BALANCE = 1000.0
FEE_RATE = 0.0005          # کارمزد معامله (اختیاری)
SLIPPAGE_RATE = 0.0002     # لغزش قیمت (اختیاری)

# لیست Symbol ها (اگر None باشد از صرافی بازارهای واجد شرایط گرفته می‌شود)
SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
]


class GateRealDataProvider(HistoricalDataProvider):
    """
    دریافت داده‌های OHLCV از GateExchange (فاز ۱۴).
    برای حجم ۲۴ ساعته از Ticker فعلی استفاده می‌کند.
    """

    def __init__(self, exchange: GateExchange):
        self.exchange = exchange

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        """دریافت OHLCV بسته‌شده از صرافی."""
        df = self.exchange.get_ohlcv(
            symbol,
            timeframe,
            limit=1000,
            closed_only=False,   # خودمان بعداً برش می‌زنیم
        )
        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if start is not None:
            df = df.loc[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df.loc[df.index <= pd.Timestamp(end)]
        return df

    def get_volume_24h_usdt(self, symbol, timestamp):
        """
        حجم ۲۴ ساعته فعلی. برای بک‌تست تاریخی دقیق نیست.
        اگر می‌خواهید Selection Bias نداشته باشید، باید از منبع
        تاریخی جداگانه استفاده کنید.
        """
        ticker = self.exchange.get_ticker(symbol)
        return ticker.get("quote_volume")


class CsvDataProvider(HistoricalDataProvider):
    """
    خواندن داده از فایل‌های CSV موجود در پوشه data/.
    حجم ۲۴ ساعته را از روی فایل volume یا به‌صورت ثابت برمی‌گرداند.
    """

    def __init__(self, symbols, volume_override=None):
        self.symbols = symbols
        self.volume_override = volume_override

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        path = os.path.join(config.DATA_DIR, f"{symbol.replace('/', '_')}_{timeframe}.csv")
        if not os.path.exists(path):
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True)

        if start is not None:
            df = df.loc[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df.loc[df.index <= pd.Timestamp(end)]
        return df

    def get_volume_24h_usdt(self, symbol, timestamp):
        if self.volume_override is not None:
            return self.volume_override
        # اگر فایل حجم جداگانه وجود دارد، اینجا بخوانید
        # فعلاً به‌صورت پیش‌فرض ۵ میلیون برمی‌گردانیم (فقط برای تست)
        return 5_000_000.0


def _select_symbols(exchange: GateExchange):
    """انتخاب Symbolهای واجد شرایط از صرافی."""
    eligible = exchange.get_eligible_markets()
    if not eligible:
        # اگر هیچ نماد واجد شرایطی نبود، از config.SYMBOL استفاده کن
        return [config.SYMBOL]
    return [market["symbol"] for market in eligible]


def main():
    print("=" * 60)
    print("REAL MARKET BACKTEST")
    print("=" * 60)

    # اتصال به صرافی (فقط خواندنی)
    exchange = GateExchange()
    print("بارگذاری بازارها...")
    exchange.load_markets()

    # انتخاب Symbolها
    if SYMBOLS:
        symbols = SYMBOLS
    else:
        symbols = _select_symbols(exchange)
        print(f"نمادهای واجد شرایط: {symbols}")

    if not symbols:
        print("هیچ نمادی برای بک‌تست وجود ندارد.")
        return

    # انتخاب Provider
    use_csv = os.getenv("USE_CSV_DATA", "false").lower() == "true"
    if use_csv:
        provider = CsvDataProvider(symbols)
        print("حالت: خواندن از CSV")
    else:
        provider = GateRealDataProvider(exchange)
        print("حالت: دریافت زنده از Gate.io (OHLCV)")

    # ساخت Runner
    runner = HistoricalBacktestRunner(
        provider,
        symbols,
        initial_balance=INITIAL_BALANCE,
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
    )

    start_ts = pd.Timestamp(BACKTEST_START)
    end_ts = pd.Timestamp(BACKTEST_END)

    print(f"بازه: {start_ts} تا {end_ts}")
    print(f"سرمایه اولیه: {INITIAL_BALANCE}")
    print("در حال اجرای بک‌تست...")

    result = runner.run(start_date=start_ts, end_date=end_ts)

    # چاپ گزارش
    print("\n" + "=" * 60)
    print("نتایج بک‌تست")
    print("=" * 60)

    metrics = result.get("metrics", {})
    print(f"تعداد کل معاملات: {result.get('total_trades', 0)}")
    print(f"تعداد سیگنال‌های انتخاب‌شده: {result.get('selected_signals', 0)}")
    print(f"تعداد Candidate ها: {result.get('total_candidates', 0)}")
    print(f"تعداد Safety Rejections: {result.get('safety_rejections', 0)}")
    print(f"سود خالص: {metrics.get('net_profit', 0.0):.2f} USDT")
    print(f"سرمایه نهایی: {metrics.get('final_balance', INITIAL_BALANCE):.2f} USDT")
    print(f"نرخ برد: {metrics.get('win_rate', 0.0)*100:.2f}%")
    print(f"Profit Factor: {metrics.get('profit_factor', float('inf')):.2f}")
    print(f"Expectancy: {metrics.get('expectancy', 0.0):.4f} R")
    print(f"Average R: {metrics.get('average_r', 0.0):.4f}")
    print(f"Max Drawdown: {metrics.get('max_drawdown', 0.0)*100:.2f}%")
    print(f"Largest Win: {metrics.get('largest_win', 0.0):.2f}")
    print(f"Largest Loss: {metrics.get('largest_loss', 0.0):.2f}")

    # تفکیک LONG/SHORT
    long_metrics = result.get("long_metrics", {})
    short_metrics = result.get("short_metrics", {})
    print("\n--- LONG ---")
    print(f"تعداد معاملات: {long_metrics.get('trades', 0)}")
    print(f"نرخ برد: {long_metrics.get('win_rate', 0.0)*100:.2f}%")
    print(f"سود خالص: {long_metrics.get('net_profit', 0.0):.2f}")

    print("\n--- SHORT ---")
    print(f"تعداد معاملات: {short_metrics.get('trades', 0)}")
    print(f"نرخ برد: {short_metrics.get('win_rate', 0.0)*100:.2f}%")
    print(f"سود خالص: {short_metrics.get('net_profit', 0.0):.2f}")

    # جزئیات معاملات
    trades = result.get("trades", [])
    if trades:
        print("\n--- ۱۰ معامله اخیر ---")
        for t in trades[-10:]:
            print(
                f"{t['symbol']} {t['direction']} "
                f"Entry={t['entry_price']:.2f} Exit={t['exit_price']:.2f} "
                f"Reason={t['exit_reason']} PnL={t['pnl']:.2f}"
            )

    print("\nبک‌تست کامل شد.")


if __name__ == "__main__":
    main()
