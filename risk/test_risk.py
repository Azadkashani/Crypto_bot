"""
فایل تست مدیریت ریسک
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk.position_sizing import RiskManager, PositionSize

def test_position_size():
    """تست محاسبه حجم معامله"""
    print("=" * 60)
    print("🔍 تست محاسبه حجم معامله")
    print("=" * 60)
    
    rm = RiskManager()
    
    # تست با موجودی ۱۰۰۰ دلار
    balance = 1000
    position_size = rm.calculate_position_size(balance)
    risk_amount = rm.calculate_risk_amount(balance)
    
    print(f"✅ موجودی کل: {balance} USDT")
    print(f"✅ حجم معامله (۲۵٪): {position_size} USDT")
    print(f"✅ مقدار ریسک (۱٪): {risk_amount} USDT")
    print(f"✅ ریسک از حجم معامله (۴٪): {position_size * 0.04} USDT")
    
    # بررسی
    assert position_size == 250, "حجم معامله باید ۲۵۰ باشد"
    assert risk_amount == 10, "ریسک باید ۱۰ باشد"
    
    print("✅ محاسبات صحیح است")
    return position_size, risk_amount

def test_leverage_calculation():
    """تست محاسبه لوریج"""
    print("\n" + "=" * 60)
    print("🔍 تست محاسبه لوریج")
    print("=" * 60)
    
    rm = RiskManager()
    
    # تست با حد ضررهای مختلف
    test_cases = [
        (0.5, 8),   # حد ضرر ۰.۵٪ -> لوریج ۸
        (1.0, 4),   # حد ضرر ۱٪ -> لوریج ۴
        (2.0, 2),   # حد ضرر ۲٪ -> لوریج ۲
        (4.0, 1),   # حد ضرر ۴٪ -> لوریج ۱
        (0.2, 20),  # حد ضرر ۰.۲٪ -> لوریج ۲۰ (حداکثر)
    ]
    
    for stop_loss_pct, expected_leverage in test_cases:
        leverage = rm.calculate_leverage(stop_loss_pct)
        print(f"✅ حد ضرر {stop_loss_pct}% -> لوریج {leverage}")
        
        # بررسی (با توجه به محدودیت حداقل و حداکثر)
        if expected_leverage == 20:
            assert leverage == 20, f"لوریج باید ۲۰ باشد، نه {leverage}"
        elif expected_leverage == 1:
            assert leverage == 1, f"لوریج باید ۱ باشد، نه {leverage}"
    
    print("✅ محاسبات لوریج صحیح است")

def test_full_position():
    """تست محاسبه کامل معامله"""
    print("\n" + "=" * 60)
    print("🔍 تست محاسبه کامل معامله")
    print("=" * 60)
    
    rm = RiskManager()
    
    # مثال: موجودی ۱۰۰۰ دلار
    total_balance = 1000
    entry_price = 100
    stop_loss_price = 99.5  # حد ضرر ۰.۵٪
    take_profit_price = 102  # حد سود ۲٪
    
    position = rm.calculate_full_position(
        total_balance=total_balance,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price
    )
    
    if position:
        print(f"✅ حجم معامله: {position.position_size} USDT")
        print(f"✅ مقدار ریسک: {position.risk_amount} USDT")
        print(f"✅ درصد حد ضرر: {position.stop_loss_pct:.2f}%")
        print(f"✅ درصد حد سود: {position.take_profit_pct:.2f}%")
        print(f"✅ لوریج: {position.leverage}")
        print(f"✅ نسبت ریسک به ریوارد: {position.risk_reward_ratio:.2f}")
        print(f"✅ مارجین مورد نیاز: {position.margin_required:.2f} USDT")
        
        # بررسی
        assert position.position_size == 250, "حجم معامله باید ۲۵۰ باشد"
        assert position.risk_amount == 10, "ریسک باید ۱۰ باشد"
        assert position.leverage == 8, "لوریج باید ۸ باشد"
        assert position.risk_reward_ratio == 4.0, "نسبت باید ۴ باشد"
        
        print("\n✅ تمام محاسبات صحیح است!")
    else:
        print("❌ معامله معتبر نیست")

def test_position_limits():
    """تست محدودیتهای پوزیشن"""
    print("\n" + "=" * 60)
    print("🔍 تست محدودیتهای پوزیشن")
    print("=" * 60)
    
    rm = RiskManager()
    
    # تست با ۴ پوزیشن باز
    open_positions = [
        {'contract': 'BTC_USDT'},
        {'contract': 'ETH_USDT'},
        {'contract': 'SOL_USDT'},
        {'contract': 'BNB_USDT'},
    ]
    
    result = rm.check_position_limits(open_positions, 'XRP_USDT')
    print(f"✅ ۴ پوزیشن باز + ارز جدید: {'مجاز' if result['allowed'] else 'غیرمجاز'}")
    print(f"   دلیل: {result['reason']}")
    
    # تست با پوزیشن تکراری
    result = rm.check_position_limits(open_positions, 'BTC_USDT')
    print(f"✅ پوزیشن تکراری روی BTC: {'مجاز' if result['allowed'] else 'غیرمجاز'}")
    print(f"   دلیل: {result['reason']}")
    
    # تست با ۳ پوزیشن باز
    open_positions_3 = open_positions[:3]
    result = rm.check_position_limits(open_positions_3, 'XRP_USDT')
    print(f"✅ ۳ پوزیشن باز + ارز جدید: {'مجاز' if result['allowed'] else 'غیرمجاز'}")
    print(f"   دلیل: {result['reason']}")

def main():
    """اجرای تمام تستها"""
    print("\n🔍 شروع تست مدیریت ریسک")
    print("=" * 60)
    
    try:
        test_position_size()
        test_leverage_calculation()
        test_full_position()
        test_position_limits()
        
        print("\n" + "=" * 60)
        print("✅ تمام تستها با موفقیت انجام شد!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ خطا: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
