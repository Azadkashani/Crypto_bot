# risk_gate.py
"""
ماژول Risk Gate برای محاسبه ورود، حد ضرر و حد سود پس از BOS.
فقط از اطلاعات موجود تا کندل BOS استفاده می‌شود.
"""

import pandas as pd
import config


def evaluate_risk(
    df: pd.DataFrame,
    bos_idx: pd.Timestamp,
    direction: str,
    rr: float = None,
) -> dict:
    """
    محاسبه ورود، حد ضرر و حد سود بر اساس آخرین swing قبل از BOS.

    پارامترها:
        df: DataFrame شامل ستون‌های swing_high، swing_low و close.
        bos_idx: ایندکس کندل BOS.
        direction: 'LONG' یا 'SHORT'.
        rr: نسبت ریسک/ریوارد. پیش‌فرض از config.

    خروجی:
        dict شامل valid, entry_price, stop_loss, take_profit, risk_reward
        و در صورت خطا reason.
    """
    if rr is None:
        rr = config.RISK_REWARD

    # بررسی وجود bos_idx در DataFrame
    if bos_idx not in df.index:
        return {"valid": False, "reason": "BOS index not found"}

    # قیمت ورود: کلوز کندل BOS
    entry_price = df.loc[bos_idx, "close"]

    # تعیین جهت معامله
    if direction == "LONG":
        swing_col = "swing_low"
        price_col = "low"
        stop_comparison = entry_price > 0  # temporary
    elif direction == "SHORT":
        swing_col = "swing_high"
        price_col = "high"
        stop_comparison = entry_price > 0  # temporary
    else:
        return {"valid": False, "reason": "Invalid direction"}

    # فیلتر swing‌های تأییدشده قبل از BOS
    prior_mask = df.index < bos_idx
    swing_indices = df.loc[prior_mask & df[swing_col], swing_col].index

    if len(swing_indices) == 0:
        if direction == "LONG":
            return {"valid": False, "reason": "No confirmed swing low before BOS"}
        else:
            return {"valid": False, "reason": "No confirmed swing high before BOS"}

    # آخرین swing قبل از BOS
    stop_loss = df.loc[swing_indices[-1], price_col]

    # محاسبه ریسک
    if direction == "LONG":
        risk = entry_price - stop_loss
        if risk <= 0:
            return {"valid": False, "reason": "Invalid stop loss (risk <= 0)"}
        take_profit = entry_price + risk * rr
    else:  # SHORT
        risk = stop_loss - entry_price
        if risk <= 0:
            return {"valid": False, "reason": "Invalid stop loss (risk <= 0)"}
        take_profit = entry_price - risk * rr

    return {
        "valid": True,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": rr,
    }
