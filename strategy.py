"""
موتور سیگنال نهایی بر اساس رژیم 4H/1H و پولبک 5M.
ترتیب الزامی: RSI → CHOCH → BOS.
"""

import pandas as pd
from datetime import timedelta
import indicators
import regime
import choch
import bos
import config


def _timeframe_to_timedelta(tf: str) -> timedelta:
    """تبدیل رشته تایم‌فریم به timedelta."""
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        raise ValueError(f"Unsupported timeframe: {tf}")


def generate_signal(df_4h: pd.DataFrame, df_1h: pd.DataFrame, df_5m: pd.DataFrame,
                    as_of: pd.Timestamp = None) -> dict:
    """
    تولید سیگنال LONG/SHORT بر اساس ترتیب تاییدشده.
    """

    def _filter_closed(df: pd.DataFrame, tf: str) -> pd.DataFrame:
        if df.empty:
            return df
        if as_of is None:
            return df
        delta = _timeframe_to_timedelta(tf)
        mask = df.index + delta <= as_of
        return df.loc[mask]

    df_4h_closed = _filter_closed(df_4h, config.TIMEFRAME_4H)
    df_1h_closed = _filter_closed(df_1h, config.TIMEFRAME_1H)
    df_5m_closed = _filter_closed(df_5m, config.TIMEFRAME_5M)

    if df_5m_closed.empty:
        return {
            "signal": "NONE",
            "valid": False,
            "reason": "Insufficient 5m data",
            "choch": False,
            "bos": False,
            "rsi_recovery": False
        }

    r4h = regime.get_regime(df_4h_closed) if not df_4h_closed.empty else regime.REGIME_RANGE
    r1h = regime.get_regime(df_1h_closed) if not df_1h_closed.empty else regime.REGIME_RANGE

    if r4h == regime.REGIME_BULLISH and r1h == regime.REGIME_BULLISH:
        direction = "LONG"
    elif r4h == regime.REGIME_BEARISH and r1h == regime.REGIME_BEARISH:
        direction = "SHORT"
    else:
        return {
            "signal": "NONE",
            "valid": False,
            "reason": "4H and 1H regimes are not aligned",
            "regime_4h": r4h,
            "regime_1h": r1h,
            "choch": False,
            "bos": False,
            "rsi_recovery": False
        }

    rsi_df = indicators.add_rsi(df_5m_closed, period=config.RSI_PERIOD)
    rsi_col = f'rsi_{config.RSI_PERIOD}'
    rsi_series = rsi_df[rsi_col].dropna()
    if len(rsi_series) < 2:
        return {
            "signal": "NONE",
            "valid": False,
            "reason": "Insufficient RSI data",
            "choch": False,
            "bos": False,
            "rsi_recovery": False
        }

    choch_df = choch.detect_choch(df_5m_closed)
    bos_df = bos.detect_bos(df_5m_closed)

    latest_5m = df_5m_closed.index[-1]
    latest_rsi = rsi_series.iloc[-1]
    previous_rsi = rsi_series.iloc[-2]

    if direction == "LONG":
        rsi_condition = (rsi_series.min() <= config.RSI_OVERSOLD) and (latest_rsi > previous_rsi)
        choch_condition = choch_df['bullish_choch'].any()
        bos_condition = bos_df['bullish_bos'].any()
    else:
        rsi_condition = (rsi_series.max() >= config.RSI_OVERBOUGHT) and (latest_rsi < previous_rsi)
        choch_condition = choch_df['bearish_choch'].any()
        bos_condition = bos_df['bearish_bos'].any()

    has_prior_choch = choch_condition

    signal_valid = direction is not None and rsi_condition and bos_condition and has_prior_choch

    if not signal_valid:
        reason_parts = []
        if not rsi_condition:
            reason_parts.append("RSI condition not met")
        if not has_prior_choch:
            reason_parts.append("CHOCH not detected")
        if not bos_condition:
            reason_parts.append("BOS not detected")
        reason = ", ".join(reason_parts) or "Conditions not met"
        return {
            "signal": "NONE",
            "valid": False,
            "reason": reason,
            "regime_4h": r4h,
            "regime_1h": r1h,
            "rsi_5m": round(latest_rsi, 2),
            "rsi_recovery": bool(rsi_condition),
            "choch": bool(has_prior_choch),
            "bos": bool(bos_condition)
        }

    return {
        "signal": direction,
        "valid": True,
        "reason": f"{direction} signal valid",
        "timeframe": "5m",
        "regime_4h": r4h,
        "regime_1h": r1h,
        "rsi_5m": round(latest_rsi, 2),
        "rsi_recovery": bool(rsi_condition),
        "choch": bool(has_prior_choch),
        "bos": bool(bos_condition),
        "timestamp": latest_5m
    }
