"""
موتور سیگنال نهایی بر اساس رژیم 4H/1H و پولبک 5M.
ترتیب الزامی: RSI → CHOCH → BOS → Risk Gate → Position Sizing.
"""

import pandas as pd
from datetime import timedelta
from typing import Optional, Dict, Any
import indicators
import regime
import choch
import bos
import config
from risk_gate import evaluate_risk
from position_sizing import calculate_position_size


def _timeframe_to_timedelta(tf: str) -> timedelta:
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


def generate_signal(
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    df_5m: pd.DataFrame,
    as_of: Optional[pd.Timestamp] = None,
    account_balance: Optional[float] = None,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """
    تولید سیگنال LONG/SHORT بر اساس توالی تأییدشده.

    پارامترها:
        df_4h, df_1h, df_5m: دیتافریم‌های مستقل.
        as_of: زمان تصمیم‌گیری (اختیاری).
        account_balance: بالانس حساب برای Position Sizing (اختیاری).
        symbol: نماد معاملاتی (اختیاری، فقط برای metadata).
    """
    if account_balance is None:
        account_balance = config.ACCOUNT_BALANCE

    def _filter_closed(df: pd.DataFrame, tf: str) -> pd.DataFrame:
        if df.empty:
            return df
        if as_of is None:
            return df
        delta = _timeframe_to_timedelta(tf)
        mask = df.index + delta <= as_of
        return df.loc[mask]

    if as_of is None:
        df_4h_closed = df_4h.copy()
        df_1h_closed = df_1h.copy()
        df_5m_closed = df_5m.copy()
    else:
        df_4h_closed = _filter_closed(df_4h, config.TIMEFRAME_4H)
        df_1h_closed = _filter_closed(df_1h, config.TIMEFRAME_1H)
        df_5m_closed = _filter_closed(df_5m, config.TIMEFRAME_5M)

    if df_5m_closed.empty:
        return {"signal": "NONE", "valid": False, "reason": "Insufficient 5m data", "choch": False, "bos": False, "rsi_recovery": False}

    r4h = regime.get_regime(df_4h_closed) if not df_4h_closed.empty else regime.REGIME_RANGE
    r1h = regime.get_regime(df_1h_closed) if not df_1h_closed.empty else regime.REGIME_RANGE

    if r4h == regime.REGIME_BULLISH and r1h == regime.REGIME_BULLISH:
        direction = "LONG"
    elif r4h == regime.REGIME_BEARISH and r1h == regime.REGIME_BEARISH:
        direction = "SHORT"
    else:
        return {"signal": "NONE", "valid": False, "reason": "4H and 1H regimes are not aligned", "regime_4h": r4h, "regime_1h": r1h, "choch": False, "bos": False, "rsi_recovery": False}

    rsi_df = indicators.add_rsi(df_5m_closed, period=config.RSI_PERIOD)
    rsi_col = f"rsi_{config.RSI_PERIOD}"
    rsi_series = rsi_df[rsi_col].dropna()
    if len(rsi_series) < 2:
        return {"signal": "NONE", "valid": False, "reason": "Insufficient RSI data", "regime_4h": r4h, "regime_1h": r1h, "choch": False, "bos": False, "rsi_recovery": False}

    choch_df = choch.detect_choch(df_5m_closed)
    bos_df = bos.detect_bos(df_5m_closed)

    if direction == "LONG":
        is_bullish = True
        rsi_zone_threshold = config.RSI_OVERSOLD
    else:
        is_bullish = False
        rsi_zone_threshold = config.RSI_OVERBOUGHT

    zone_mask = rsi_series <= rsi_zone_threshold if is_bullish else rsi_series >= rsi_zone_threshold
    zone_indices = rsi_series.index[zone_mask].tolist()
    if not zone_indices:
        return {"signal": "NONE", "valid": False, "reason": "RSI condition not met", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": False, "choch": False, "bos": False}

    first_zone_idx = zone_indices[0]
    first_zone_pos = rsi_series.index.get_loc(first_zone_idx)

    recovery_idx = None
    for pos in range(first_zone_pos + 1, len(rsi_series)):
        if is_bullish:
            if rsi_series.iloc[pos] > rsi_series.iloc[pos - 1]:
                recovery_idx = rsi_series.index[pos]
                break
        else:
            if rsi_series.iloc[pos] < rsi_series.iloc[pos - 1]:
                recovery_idx = rsi_series.index[pos]
                break

    if recovery_idx is None:
        return {"signal": "NONE", "valid": False, "reason": "RSI recovery not detected", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": False, "choch": False, "bos": False}

    choch_flags = choch_df["bullish_choch"] if is_bullish else choch_df["bearish_choch"]
    bos_flags = bos_df["bullish_bos"] if is_bullish else bos_df["bearish_bos"]

    choch_candidates = choch_flags.index[choch_flags & (choch_flags.index >= recovery_idx)].tolist()
    if not choch_candidates:
        return {"signal": "NONE", "valid": False, "reason": "CHOCH not detected", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": True, "choch": False, "bos": False}

    choch_idx = choch_candidates[0]
    bos_candidates = bos_flags.index[bos_flags & (bos_flags.index >= choch_idx)].tolist()
    if not bos_candidates:
        return {"signal": "NONE", "valid": False, "reason": "BOS not detected", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": True, "choch": True, "bos": False}

    bos_idx = bos_candidates[0]

    risk_result = evaluate_risk(bos_df, bos_idx, direction, rr=config.RISK_REWARD)
    if not risk_result["valid"]:
        return {"signal": "NONE", "valid": False, "reason": f"Risk gate: {risk_result['reason']}", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": True, "choch": True, "bos": True}

    position_result = calculate_position_size(
        account_balance=account_balance,
        risk_per_trade=config.RISK_PER_TRADE,
        entry_price=risk_result["entry_price"],
        stop_loss=risk_result["stop_loss"],
        leverage=config.LEVERAGE,
    )
    if not position_result["valid"]:
        return {"signal": "NONE", "valid": False, "reason": f"Position sizing: {position_result['reason']}", "regime_4h": r4h, "regime_1h": r1h, "rsi_5m": round(rsi_series.iloc[-1], 2), "rsi_recovery": True, "choch": True, "bos": True}

    latest_5m = df_5m_closed.index[-1]
    latest_rsi = rsi_series.iloc[-1]

    return {
        "signal": direction,
        "valid": True,
        "reason": f"{direction} signal valid",
        "timeframe": "5m",
        "regime_4h": r4h,
        "regime_1h": r1h,
        "rsi_5m": round(latest_rsi, 2),
        "rsi_recovery": True,
        "choch": True,
        "bos": True,
        "entry_price": risk_result["entry_price"],
        "stop_loss": risk_result["stop_loss"],
        "take_profit": risk_result["take_profit"],
        "risk_reward": risk_result["risk_reward"],
        "risk_amount": position_result["risk_amount"],
        "stop_distance": position_result["stop_distance"],
        "position_size": position_result["position_size"],
        "position_value": position_result["position_value"],
        "margin_required": position_result["margin_required"],
        "leverage": position_result["leverage"],
        "timestamp": latest_5m,
        "symbol": symbol,
    }
