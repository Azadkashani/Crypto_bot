from src.detection.whale_detector import WhaleDetector
from src.detection.excluded_addresses import ExcludedAddressRegistry
def test_candidate():
    reg = ExcludedAddressRegistry()
    detector = WhaleDetector(reg)
    stats = {'total_volume_usd': 2_000_000, 'average_trade_size_usd': 50_000,
             'largest_trade_size_usd': 100_000, 'buy_volume_usd': 1_500_000,
             'swap_count': 10, 'unique_dexes': 1, 'balance_usd': 0}
    assert detector.is_candidate(stats) == True
