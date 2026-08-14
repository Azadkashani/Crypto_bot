"""
ماژول Position Sizing و محاسبه لوریج داینامیک.
"""

from __future__ import annotations

import math
from typing import Dict, Any, Optional


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss: float,
    allocation: float = 0.25,
    max_leverage: float = 20.0,
) -> Dict[str, Any]:
    """
    محاسبه حجم معامله، مارجین و لوریج موردنیاز.

    ریسک هر معامله = account_balance * risk_per_trade
    مارجین مجاز = account_balance * allocation
    لوریج = risk_amount / (margin_allocation * stop_distance_pct)

    خروجی شامل:
        valid, risk_amount, margin_allocation, required_leverage, leverage,
        notional_position_value, position_size, position_value,
        stop_distance, stop_distance_pct, expected_loss_at_sl
    """
    # اعتبارسنجی ورودی‌ها
    if account_balance <= 0:
        return {"valid": False, "reason": "Account balance must be positive"}
    if risk_per_trade <= 0 or risk_per_trade >= 1:
        return {"valid": False, "reason": "Risk per trade must be between 0 and 1"}
    if allocation <= 0 or allocation > 1:
        return {"valid": False, "reason": "Allocation must be between 0 and 1"}
    if entry_price <= 0 or stop_loss <= 0:
        return {"valid": False, "reason": "Entry and stop loss must be positive"}
    if entry_price == stop_loss:
        return {"valid": False, "reason": "Entry price equals stop loss"}
    if max_leverage <= 0:
        return {"valid": False, "reason": "Max leverage must be positive"}

    # محاسبه ریسک و مارجین
    risk_amount = account_balance * risk_per_trade
    margin_allocation = account_balance * allocation

    # فاصله حد ضرر
    stop_distance = abs(entry_price - stop_loss)
    stop_distance_pct = stop_distance / entry_price
    if stop_distance_pct <= 0:
        return {"valid": False, "reason": "Invalid stop distance"}

    # لوریج موردنیاز
    required_leverage = risk_amount / (margin_allocation * stop_distance_pct)

    if required_leverage > max_leverage:
        return {
            "valid": False,
            "reason": f"Required leverage ({required_leverage:.2f}x) exceeds max leverage ({max_leverage}x)",
        }

    leverage = required_leverage
    notional_position_value = margin_allocation * leverage
    position_size = notional_position_value / entry_price
    position_value = position_size * entry_price

    # زیان مورد انتظار در SL
    expected_loss_at_sl = notional_position_value * stop_distance_pct

    # تأیید تطابق ریسک
    if not math.isclose(expected_loss_at_sl, risk_amount, rel_tol=0.01):
        return {
            "valid": False,
            "reason": "Risk mismatch after calculation",
        }

    return {
        "valid": True,
        "risk_amount": risk_amount,
        "margin_allocation": margin_allocation,
        "required_leverage": required_leverage,
        "leverage": leverage,
        "notional_position_value": notional_position_value,
        "position_size": position_size,
        "position_value": position_value,
        "stop_distance": stop_distance,
        "stop_distance_pct": stop_distance_pct,
        "expected_loss_at_sl": expected_loss_at_sl,
    }
