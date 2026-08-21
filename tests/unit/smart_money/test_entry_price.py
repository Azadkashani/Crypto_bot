from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_entry_price_missing():
    provider = MockPriceProvider({})
    event = BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                     block_number=1, timestamp=datetime(2024,1,1,tzinfo=UTC),
                     entry_price=None, entry_usd_value=None, amount=None, confidence=90)
    ev = evaluate_buy_event(event, provider, [], as_of=datetime(2024,1,2,tzinfo=UTC))
    assert ev.evaluation_status == "UNAVAILABLE"
