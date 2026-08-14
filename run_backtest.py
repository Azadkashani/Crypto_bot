#!/usr/bin/env python3
"""
اجرای Real Market Historical Backtest روی چند نماد اصلی Gate.io Futures.

این اسکریپت:
    - بازارهای واجد شرایط را بررسی می‌کند.
    - داده 5m/1h/4h واقعی را با Pagination دانلود می‌کند.
    - داده‌ها را validation کرده و در data/ ذخیره می‌کند.
    - بک‌تست چندنمادی را با HistoricalBacktestRunner اجرا می‌کند.
    - گزارش Per-Symbol و Combined را چاپ می‌کند.

هیچ سفارش واقعی ارسال نمی‌شود.
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from gate_exchange import GateExchange
from historical_data import HistoricalDataDownloader, validate_ohlcv, expected_candles
from historical_backtest import HistoricalBacktestRunner, HistoricalDataProvider
import config


# ---------- تنظیمات بک‌تست ----------
BACKTEST_START = os.getenv("BACKTEST_START", "2025-01-01T00:00:00+00:00")
BACKTEST_END = os.getenv("BACKTEST_END", "2026-01-01T00:00:00+00:00")

DATA_DIR = "data"

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "SOL/USDT:USDT",
]

TIMEFRAMES = ["5m", "1h", "4h"]

INITIAL_BALANCE = 1000.0
FEE_RATE = 0.0005
SLIPPAGE_RATE = 0.0002


class CsvHistoricalDataProvider(HistoricalDataProvider):
    """تأمین‌کننده داده تاریخی از فایل‌های CSV ذخیره‌شده."""

    def __init__(self, exchange, symbols, data_dir):
        self.exchange = exchange
        self.data = {}
        self.volume_cache = {}
        for sym in symbols:
            self.data[sym] = {}
            for tf in TIMEFRAMES:
                safe = sym.replace('/', '_').replace(':', '_')
                path = os.path.join(data_dir, f"{safe}_{tf}.csv")
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Missing CSV for {sym} {tf}")
                df = pd.read_csv(path, index_col=0, parse_dates=True)
                df.index = pd.to_datetime(df.index, utc=True)
                self.data[sym][tf] = df
            # حجم فعلی به‌عنوان proxy (محدودیت تاریخی)
            try:
                ticker = exchange.get_ticker(sym)
                self.volume_cache[sym] = float(ticker.get('quote_volume', 0))
            except Exception:
                self.volume_cache[sym] = None

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe)
        if df is None:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        return df.copy()

    def get_volume_24h_usdt(self, symbol, timestamp):
        return self.volume_cache.get(symbol)


def main():
    print("=" * 70)
    print("REAL MARKET BACKTEST")
    print("=" * 70)

    start_ts = pd.Timestamp(BACKTEST_START)
    end_ts = pd.Timestamp(BACKTEST_END)
    duration = end_ts - start_ts
    print(f"Backtest Period: {start_ts} → {end_ts}")
    print(f"Duration: {duration}")
    print(f"Initial Balance: {INITIAL_BALANCE}")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print()

    exchange = GateExchange()
    print("بارگذاری بازارها...")
    exchange.load_markets()

    eligible_symbols = []
    data_report = {}

    for sym in SYMBOLS:
        # بررسی واجد شرایط بودن بازار
        eligibility = exchange.is_market_eligible(sym)
        if not eligibility.get("eligible"):
            print(f"❌ {sym}: REJECTED - {eligibility.get('reason')}")
            continue

        eligible_symbols.append(sym)
        print(f"✅ {sym}: eligible (volume={eligibility.get('volume_24h_usdt', 0):,.0f} USDT)")

        for tf in TIMEFRAMES:
            downloader = HistoricalDataDownloader(exchange, sym, tf, start_ts, end_ts)
            df = downloader.download()
            validation = validate_ohlcv(df, tf, start_ts, end_ts)
            data_report[f"{sym}:{tf}"] = validation

            if not validation['valid']:
                print(f"   ⚠️ {tf}: INVALID - {validation['issues']}")
                continue

            downloader.save(df, DATA_DIR)
            expected = expected_candles(start_ts, end_ts, tf)
            print(f"   📦 {tf}: {len(df)} candles (expected ~{expected}) saved")

    if not eligible_symbols:
        print("\nهیچ نماد واجد شرایطی برای بک‌تست وجود ندارد.")
        return

    print("\n" + "=" * 70)
    print("اجرای بک‌تست...")
    print("=" * 70)

    provider = CsvHistoricalDataProvider(exchange, eligible_symbols, DATA_DIR)
    runner = HistoricalBacktestRunner(
        provider,
        eligible_symbols,
        initial_balance=INITIAL_BALANCE,
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
    )

    result = runner.run(start_date=start_ts, end_date=end_ts)

    # ---------- گزارش نهایی ----------
    print("\n" + "=" * 70)
    print("COMBINED RESULTS")
    print("=" * 70)

    metrics = result.get("metrics", {})
    print(f"Symbols Tested: {', '.join(eligible_symbols)}")
    print(f"Total Trades: {result.get('total_trades', 0)}")
    print(f"Selected Signals: {result.get('selected_signals', 0)}")
    print(f"Candidates: {result.get('total_candidates', 0)}")
    print(f"Safety Rejections: {result.get('safety_rejections', 0)}")
    print(f"Win Rate: {metrics.get('win_rate', 0.0)*100:.2f}%")
    print(f"Profit Factor: {metrics.get('profit_factor', float('inf')):.2f}")
    print(f"Expectancy: {metrics.get('expectancy', 0.0):.4f} R")
    print(f"Average R: {metrics.get('average_r', 0.0):.4f}")
    print(f"Net Profit: {metrics.get('net_profit', 0.0):.2f} USDT")
    print(f"Final Balance: {metrics.get('final_balance', INITIAL_BALANCE):.2f} USDT")
    print(f"Max Drawdown: {metrics.get('max_drawdown', 0.0)*100:.2f}%")
    print(f"Largest Win: {metrics.get('largest_win', 0.0):.2f}")
    print(f"Largest Loss: {metrics.get('largest_loss', 0.0):.2f}")
    print(f"Max Consecutive Wins: {metrics.get('max_consecutive_wins', 0)}")
    print(f"Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0)}")
    print(f"Recovery Factor: {metrics.get('recovery_factor', 0.0):.2f}")

    # تفکیک LONG/SHORT
    long_m = result.get("long_metrics", {})
    short_m = result.get("short_metrics", {})
    print("\n--- LONG ---")
    print(f"Trades: {long_m.get('trades', 0)} | Win Rate: {long_m.get('win_rate', 0)*100:.2f}% | Net Profit: {long_m.get('net_profit', 0):.2f}")
    print("\n--- SHORT ---")
    print(f"Trades: {short_m.get('trades', 0)} | Win Rate: {short_m.get('win_rate', 0)*100:.2f}% | Net Profit: {short_m.get('net_profit', 0):.2f}")

    # گزارش هر Symbol
    symbol_metrics = result.get("symbol_metrics", {})
    print("\n--- Per Symbol ---")
    for sym in eligible_symbols:
        sm = symbol_metrics.get(sym, {})
        print(f"{sym}: Trades={sm.get('trades', 0)}, WinRate={sm.get('win_rate', 0)*100:.1f}%, NetProfit={sm.get('net_profit', 0):.2f}, AvgR={sm.get('average_r', 0):.3f}")

    print("\nبک‌تست کامل شد.")


if __name__ == "__main__":
    main()
