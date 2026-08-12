from __future__ import annotations

import time
from pathlib import Path

import ccxt
import pandas as pd


EXCHANGE_ID = "gate"
QUOTE_CURRENCY = "USDT"

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
]

TIMEFRAMES = {
    "5m": "5m",
    "1h": "1h",
    "4h": "4h",
}

LIMIT = 1000
DATA_DIR = Path("/root/Robot_trader/data")


def create_exchange() -> ccxt.Exchange:
    exchange_class = getattr(ccxt, EXCHANGE_ID)

    exchange = exchange_class(
        {
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
            },
        }
    )

    exchange.load_markets()
    return exchange


def get_active_linear_usdt_perpetuals(exchange: ccxt.Exchange) -> list[str]:
    symbols = []

    for symbol, market in exchange.markets.items():
        if not market.get("active"):
            continue

        if market.get("type") != "swap":
            continue

        if not market.get("linear"):
            continue

        if market.get("quote") != QUOTE_CURRENCY:
            continue

        symbols.append(symbol)

    return sorted(symbols)


def fetch_ohlcv(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    limit: int = LIMIT,
) -> pd.DataFrame:

    rows = exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=limit,
    )

    if not rows:
        raise RuntimeError(
            f"No OHLCV data returned for {symbol} {timeframe}"
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="ms",
        utc=True,
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = (
        df.dropna()
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


def save_dataframe(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> Path:

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_symbol = symbol.replace("/", "_").replace(":", "_")

    path = DATA_DIR / f"{safe_symbol}_{timeframe}.csv"

    df.to_csv(
        path,
        index=False,
    )

    return path


def main() -> None:

    print("=" * 70)
    print("Crypto AI Trader - Phase 1 Data Engine")
    print("=" * 70)

    exchange = create_exchange()

    active_markets = get_active_linear_usdt_perpetuals(
        exchange
    )

    print(
        f"Active linear USDT perpetual markets: "
        f"{len(active_markets)}"
    )

    for symbol in SYMBOLS:

        if symbol not in exchange.markets:
            print(
                f"[SKIP] {symbol}: "
                f"not found in Gate markets"
            )
            continue

        market = exchange.markets[symbol]

        if not market.get("active"):
            print(
                f"[SKIP] {symbol}: inactive"
            )
            continue

        if market.get("type") != "swap":
            print(
                f"[SKIP] {symbol}: not a swap"
            )
            continue

        if not market.get("linear"):
            print(
                f"[SKIP] {symbol}: not linear"
            )
            continue

        if market.get("quote") != QUOTE_CURRENCY:
            print(
                f"[SKIP] {symbol}: quote is "
                f"{market.get('quote')}"
            )
            continue

        print()
        print(f"--- {symbol} ---")
        print(
            f"contractSize={market.get('contractSize')} "
            f"minAmount={market.get('limits', {}).get('amount', {}).get('min')}"
        )

        for timeframe in TIMEFRAMES.values():

            try:

                df = fetch_ohlcv(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                )

                path = save_dataframe(
                    df=df,
                    symbol=symbol,
                    timeframe=timeframe,
                )

                first_time = df["timestamp"].iloc[0]
                last_time = df["timestamp"].iloc[-1]

                print(
                    f"[OK] {timeframe} | "
                    f"candles={len(df)} | "
                    f"first={first_time} | "
                    f"last={last_time} | "
                    f"saved={path}"
                )

            except Exception as exc:

                print(
                    f"[ERROR] {symbol} {timeframe}: "
                    f"{type(exc).__name__}: {exc}"
                )

            time.sleep(
                exchange.rateLimit / 1000
            )

    print()
    print("=" * 70)
    print("Phase 1 Data Engine completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
