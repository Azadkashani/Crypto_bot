"""
فایل تست سیستم امتیازدهی
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.signal_scorer import SignalScorer

def test_basic_scoring():
    """تست امتیازدهی پایه"""
    print("=" * 60)
    print("🔍 تست سیستم امتیازدهی")
    print("=" * 60)
    
    # ساخت سیستم امتیازدهی
    scorer = SignalScorer()
    print("✅ سیستم امتیازدهی ساخته شد")
    
    # تست سیگنال قوی
    strong_signal = {
        'primary_trend': 1,
        'confirmation_trend': 1,
        'fear_greed_value': 20,
        'rr_ratio': 3.0,
        'news_sentiment': 'positive',
        'indicators': {
            'ema_aligned': True,
            'adx_confirmed': True,
            'bb_confirmed': True,
            'volume_confirmed': True,
        },
        'adx_value': 35,
    }
    
    result = scorer.score_signal(strong_signal)
    
    print(f"\n📊 سیگنال قوی:")
    print(f"   امتیاز کل: {result['total_score']:.2%}")
    print(f"   قبول: {'✅' if result['passed'] else '❌'}")
    print(f"\n   جزئیات:")
    for key, detail in result['details'].items():
        print(f"   - {key}: {detail['raw_score']:.2f} (وزن: {detail['weight']:.0%})")
    
    # تست سیگنال ضعیف
    weak_signal = {
        'primary_trend': 1,
        'confirmation_trend': -1,
        'fear_greed_value': 80,
        'rr_ratio': 1.0,
        'news_sentiment': 'negative',
        'indicators': {
            'ema_aligned': False,
            'adx_confirmed': False,
            'bb_confirmed': False,
            'volume_confirmed': False,
        },
        'adx_value': 15,
    }
    
    result = scorer.score_signal(weak_signal)
    
    print(f"\n📊 سیگنال ضعیف:")
    print(f"   امتیاز کل: {result['total_score']:.2%}")
    print(f"   قبول: {'✅' if result['passed'] else '❌'}")
    
    return result

def test_individual_scores():
    """تست امتیازهای جداگانه"""
    print("\n" + "=" * 60)
    print("🔍 تست امتیازهای جداگانه")
    print("=" * 60)
    
    scorer = SignalScorer()
    
    # تست هم‌جهتی تایم‌فریم
    print(f"\n✅ هم‌جهتی تایم‌فریم:")
    print(f"   هم‌جهت: {scorer.score_timeframe_alignment(1, 1)}")
    print(f"   خنثی: {scorer.score_timeframe_alignment(1, 0)}")
    print(f"   خلاف: {scorer.score_timeframe_alignment(1, -1)}")
    
    # تست احساسات بازار
    print(f"\n✅ احساسات بازار:")
    print(f"   ترس شدید (20): {scorer.score_market_sentiment(20)}")
    print(f"   خنثی (50): {scorer.score_market_sentiment(50)}")
    print(f"   طمع شدید (80): {scorer.score_market_sentiment(80)}")
    
    # تست ریسک به ریوارد
    print(f"\n✅ ریسک به ریوارد:")
    print(f"   عالی (4.0): {scorer.score_risk_reward(4.0)}")
    print(f"   خوب (2.0): {scorer.score_risk_reward(2.0)}")
    print(f"   ضعیف (1.0): {scorer.score_risk_reward(1.0)}")
    
    # تست قدرت روند
    print(f"\n✅ قدرت روند:")
    print(f"   قوی (40): {scorer.score_trend_strength(40)}")
    print(f"   متوسط (25): {scorer.score_trend_strength(25)}")
    print(f"   ضعیف (15): {scorer.score_trend_strength(15)}")

def main():
    """اجرای تمام تست‌ها"""
    print("\n🔍 شروع تست سیستم امتیازدهی")
    print("=" * 60)
    
    try:
        test_basic_scoring()
        test_individual_scores()
        
        print("\n" + "=" * 60)
        print("✅ تمام تست‌ها با موفقیت انجام شد!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ خطا: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
