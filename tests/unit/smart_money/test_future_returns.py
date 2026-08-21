from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_return_1h():
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
    ev = evaluate_buy_event(event, provider, horizons, as_of=datetime(2024,1,1,13,0,tzinfo=UTC))
    assert ev.returns["1h"] == 10.0
    assert ev.win_flags["1h"] == True
