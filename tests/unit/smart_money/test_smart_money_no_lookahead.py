from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_future_price_not_used_before_asof():
    provider = MockPriceProvider({
        "TOKEN": [
            (int(datetime(2024,1,1,12,0,tzinfo=UTC).timestamp()), 100.0),
            (int(datetime(2024,1,1,13,0,tzinfo=UTC).timestamp()), 110.0),
        ]
    })
    event = BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                     block_number=1, timestamp=datetime(2024,1,1,12,0,tzinfo=UTC),
                     entry_price=100.0, entry_usd_value=None, amount=None, confidence=90)
    horizons = [("1h", timedelta(hours=1))]
    # as_of = 12:30, so 1h target 13:00 > as_of => cannot evaluate
    ev = evaluate_buy_event(event, provider, horizons, as_of=datetime(2024,1,1,12,30,tzinfo=UTC))
    assert ev.returns["1h"] is None
    assert ev.win_flags["1h"] is None
