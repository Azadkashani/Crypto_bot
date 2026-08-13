# position_sizing.py
"""
ماژول Position Sizing و مدیریت ریسک پایه.
این ماژول هیچ اتصال صرافی انجام نمی‌دهد و فقط محاسبات ریاضی انجام می‌دهد.
"""


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss: float,
    leverage: float,
) -> dict:
    """
    محاسبه حجم معامله بر اساس ریسک معین از حساب.

    پارامترها:
        account_balance: موجودی حساب (USDT).
        risk_per_trade: درصد ریسک از حساب (مثلاً 0.01 برای ۱٪).
        entry_price: قیمت ورود.
        stop_loss: قیمت حد ضرر.
        leverage: اهرم معامله.

    خروجی:
        dict شامل:
            valid, risk_amount, stop_distance, position_size,
            position_value, margin_required, leverage
        و در صورت خطا reason.

    توجه:
        اهرم فقط margin_required را تغییر می‌دهد و تأثیری روی risk_amount ندارد.
    """
    # اعتبارسنجی ورودی‌ها
    if account_balance <= 0:
        return {"valid": False, "reason": "Account balance must be positive"}

    if risk_per_trade <= 0 or risk_per_trade >= 1:
        return {"valid": False, "reason": "Risk per trade must be between 0 and 1"}

    if entry_price <= 0:
        return {"valid": False, "reason": "Entry price must be positive"}

    if stop_loss <= 0:
        return {"valid": False, "reason": "Stop loss must be positive"}

    if entry_price == stop_loss:
        return {"valid": False, "reason": "Entry price equals stop loss"}

    if leverage <= 0:
        return {"valid": False, "reason": "Leverage must be positive"}

    # مقدار ریسک (USDT)
    risk_amount = account_balance * risk_per_trade

    # فاصله حد ضرر
    stop_distance = abs(entry_price - stop_loss)

    if stop_distance <= 0:
        return {"valid": False, "reason": "Stop distance must be positive"}

    # حجم معامله (تعداد قرارداد/کوین)
    position_size = risk_amount / stop_distance

    # ارزش معامله
    position_value = position_size * entry_price

    # مارجین مورد نیاز
    margin_required = position_value / leverage

    return {
        "valid": True,
        "risk_amount": risk_amount,
        "stop_distance": stop_distance,
        "position_size": position_size,
        "position_value": position_value,
        "margin_required": margin_required,
        "leverage": leverage,
    }
