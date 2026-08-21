from src.smart_money.smart_money_scorer import compute_smart_money_score

def test_insufficient_data():
    res = compute_smart_money_score(win_rate=90, avg_return=10, profit_factor=2.0,
                                    timing_accuracy=80, entry_quality=70, mfe_mae_score=60,
                                    consistency_score=50, sample_size=5, min_events=10)
    assert res['status'] == 'INSUFFICIENT_DATA'
    assert res['score'] < res['raw_score']

def test_full_score():
    # ورودی‌های بالا برای کسب امتیاز GOOD به بالا
    res = compute_smart_money_score(win_rate=95, avg_return=80, profit_factor=3.0,
                                    timing_accuracy=90, entry_quality=90, mfe_mae_score=80,
                                    consistency_score=80, sample_size=20, min_events=10)
    assert res['score'] > 0
    assert res['status'] in ['GOOD', 'STRONG', 'EXCEPTIONAL']
