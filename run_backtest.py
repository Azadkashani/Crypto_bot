#!/usr/bin/env python3
"""
اجرای Real Market Historical Backtest روی داده‌های واقعی Gate.io Futures.

این اسکریپت:
    - بازارهای ۵ نماد اصلی را بررسی می‌کند.
    - برای هر Symbol و Timeframe داده تاریخی را دانلود یا از CSV محلی می‌خواند.
    - اعتبارسنجی کامل داده انجام می‌دهد.
    - فقط در صورت کامل بودن همه داده‌ها، بک‌تست را اجرا می‌کند.
    - از نسخه بهینه‌شده موتور بک‌تست استفاده می‌کند.
    - در پایان، جزئیات تمام معاملات را به‌صورت جدول نمایش می‌دهد.

هیچ سفارش واقعی ارسال نمی‌شود.
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from gate_exchange import GateExchange
from historical_data import (
    HistoricalDataDownloader,
    validate_ohlcv,
    validate_coverage,
    load_local_csv,
    save_csv,
    DataCoverageError,
    timeframe_to_timedelta,
)
from backtest_engine import OptimizedBacktestRunner
from historical_backtest import HistoricalDataProvider

# ---------------------------------------------------------------
# تنظیمات بک‌تست
# ---------------------------------------------------------------
NOW = pd.Timestamp.now(tz='UTC')
BACKTEST_END = NOW.floor('4h') - pd.Timedelta(hours=4)
BACKTEST_START = BACKTEST_END - pd.Timedelta(days=30)

if os.getenv("BACKTEST_START"):
    BACKTEST_START = pd.Timestamp(os.getenv("BACKTEST_START"))
if os.getenv("BACKTEST_END"):
    BACKTEST_END = pd.Timestamp(os.getenv("BACKTEST_END"))

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

WARMUP_BARS = {
    "5m": 500,
    "1h": 300,
    "4h": 300,
}


class DictHistoricalDataProvider(HistoricalDataProvider):
    """
    Provider ساده بر پایه دیتافریم‌های ذخیره‌شده در حافظه.
    """

    def __init__(self, data: dict, volume_cache: dict):
        self.data = data
        self.volume_cache = volume_cache

    def get_ohlcv(self, symbol, timeframe, start=None, end=None):
        df = self.data.get(symbol, {}).get(timeframe)
        if df is None:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
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
    print(f"Backtest Period: {BACKTEST_START} → {BACKTEST_END}")
    print(f"Duration: {BACKTEST_END - BACKTEST_START}")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print()

    exchange = GateExchange()
    print("بارگذاری بازارها...")
    exchange.load_markets()

    data_store = {}
    volume_cache = {}
    errors = []

    for sym in SYMBOLS:
        eligibility = exchange.is_market_eligible(sym)
        if not eligibility.get("eligible"):
            print(f"❌ {sym}: REJECTED - {eligibility.get('reason')}")
            errors.append(f"{sym}: market not eligible")
            continue

        print(f"\n✅ {sym}: eligible")
        data_store[sym] = {}
        try:
            ticker = exchange.get_ticker(sym)
            volume_cache[sym] = float(ticker.get("quote_volume", 0))
        except Exception as e:
            volume_cache[sym] = None
            print(f"   ⚠️ unable to fetch current volume: {e}")

        for tf in TIMEFRAMES:
            warmup_delta = timedelta(
                seconds=WARMUP_BARS[tf] * timeframe_to_timedelta(tf).total_seconds()
            )
            data_start = BACKTEST_START - warmup_delta

            df = None
            local_df = load_local_csv(sym, tf, DATA_DIR)

            if local_df is not None:
                local_validation = validate_ohlcv(local_df, tf)
                local_coverage = validate_coverage(local_df, tf, data_start, BACKTEST_END)
                if local_validation["valid"] and local_coverage["coverage_ok"]:
                    df = local_df.loc[
                        (local_df.index >= data_start) & (local_df.index <= BACKTEST_END)
                    ]
                    print(f"   📦 {tf}: using local CSV ({len(df)} rows)")
                else:
                    print(f"   ⚠️ {tf}: local CSV invalid or insufficient; will try download")
                    print(f"       validation: {local_validation['issues']}")
                    print(f"       coverage: {local_coverage.get('reason')}")

            if df is None:
                try:
                    downloader = HistoricalDataDownloader(
                        exchange,
                        sym,
                        tf,
                        data_start,
                        BACKTEST_END,
                    )
                    df = downloader.download()
                    validation = validate_ohlcv(df, tf)
                    coverage = validate_coverage(df, tf, data_start, BACKTEST_END)
                    if not validation["valid"] or not coverage["coverage_ok"]:
                        raise DataCoverageError(
                            f"validation failed: {validation['issues']}, coverage: {coverage['reason']}"
                        )
                    save_csv(df, sym, tf, DATA_DIR)
                    print(f"   📥 {tf}: downloaded ({len(df)} rows)")
                except DataCoverageError as e:
                    print(f"   ❌ {tf}: {e}")
                    errors.append(f"{sym} {tf}: {e}")
                    df = None

            if df is None:
                continue

            data_store[sym][tf] = df

        if not data_store[sym]:
            print(f"   ❌ {sym}: no valid data")
        else:
            print(f"   ✅ {sym}: all data present")

    if errors:
        print("\n" + "=" * 70)
        print("BACKTEST BLOCKED")
        print("=" * 70)
        for err in errors:
            print(f" - {err}")
        print("\nهیچ بک‌تستی اجرا نشد تا از نتایج گمراه‌کننده جلوگیری شود.")
        return

    print("\n" + "=" * 70)
    print("اجرای بک‌تست بهینه‌شده...")
    print("=" * 70)

    provider = DictHistoricalDataProvider(data_store, volume_cache)
    runner = OptimizedBacktestRunner(
        provider,
        SYMBOLS,
        initial_balance=INITIAL_BALANCE,
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
    )

    result = runner.run(start_date=BACKTEST_START, end_date=BACKTEST_END)

    print("\n" + "=" * 70)
    print("COMBINED RESULTS")
    print("=" * 70)

    metrics = result.get("metrics", {})
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

    # نمایش جزئیات معاملات
    trades = result.get("trades", [])
    if trades:
        print("\n" + "=" * 180)
        print("TRADE DETAILS")
        print("=" * 180)
        print(
            f"{'#':<4} {'Symbol':<18} {'Dir':<6} {'Entry Time':<20} {'Entry':>12} {'SL':>12} {'TP':>12} {'Size':>10} {'Risk':>8} {'Lev':>6} {'Exit Time':<20} {'Exit':>12} {'Reason':<6} {'PnL':>10} {'R':>7}"
        )
        print("-" * 180)
        for i, t in enumerate(trades, 1):
            entry_time = t.get("entry_time")
            exit_time = t.get("exit_time")
            entry_time_str = str(entry_time)[:19] if entry_time else "N/A"
            exit_time_str = str(exit_time)[:19] if exit_time else "N/A"
            print(
                f"{i:<4} "
                f"{t.get('symbol',''):<18} "
                f"{t.get('direction',''):<6} "
                f"{entry_time_str:<20} "
                f"{t.get('entry_price',0):>12.2f} "
                f"{t.get('stop_loss',0):>12.2f} "
                f"{t.get('take_profit',0):>12.2f} "
                f"{t.get('position_size',0):>10.6f} "
                f"{t.get('risk_amount',0):>8.2f} "
                f"{t.get('leverage',0):>6.2f} "
                f"{exit_time_str:<20} "
                f"{t.get('exit_price',0):>12.2f} "
                f"{t.get('exit_reason',''):<6} "
                f"{t.get('pnl',0):>10.2f} "
                f"{t.get('r_multiple',0):>7.2f}"
            )
        print("=" * 180)

    print("\nبک‌تست کامل شد.")


if __name__ == "__main__":
    main()
