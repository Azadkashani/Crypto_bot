from src.scoring.whale_scorer import compute_whale_score
def test_score():
    stats = {'total_volume_usd': 10_000_000, 'average_trade_size_usd': 500_000,
             'largest_trade_size_usd': 2_000_000, 'swap_count': 100,
             'unique_dexes': 5, 'balance_usd': 5_000_000}
    score = compute_whale_score(stats)
    assert 0 <= score <= 100
