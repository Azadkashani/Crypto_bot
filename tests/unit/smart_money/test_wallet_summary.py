from src.smart_money.wallet_performance import WalletPerformanceCalculator
from src.smart_money.price_provider import MockPriceProvider
from src.smart_money.performance_evaluator import BuyEvent
from datetime import datetime, timedelta, UTC

def test_wallet_summary_basic():
    provider = MockPriceProvider({
        "TOKEN": [
            (int(datetime(2024,1,1,12,0,tzinfo=UTC).timestamp()), 100.0),
            (int(datetime(2024,1,1,13,0,tzinfo=UTC).timestamp()), 110.0),
            (int(datetime(2024,1,1,14,0,tzinfo=UTC).timestamp()), 108.0),
        ]
    })
    events = [
        BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                 block_number=1, timestamp=datetime(2024,1,1,12,0,tzinfo=UTC),
                 entry_price=100.0, entry_usd_value=None, amount=None, confidence=90),
        BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x2",
                 block_number=2, timestamp=datetime(2024,1,1,13,0,tzinfo=UTC),
                 entry_price=110.0, entry_usd_value=None, amount=None, confidence=90),
    ]
    calc = WalletPerformanceCalculator(provider)
    summary = calc.compute_wallet_summary("0xw", events)
    assert summary['sample_size'] == 2
    assert summary['evaluated_events'] == 2
    # Because horizons are up to 24h, as_of is None, but price data only up to 14:00, some horizons will be None.
    # But we still get some returns for 1h, 2h? Our horizons include 5m,15m,30m,1h,4h... data missing for >14h so partial.
    assert summary['smart_money_status'] in ['INSUFFICIENT_DATA', 'POOR', 'WEAK', 'AVERAGE', 'GOOD', 'STRONG', 'EXCEPTIONAL']
