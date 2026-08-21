import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def test_no_lookahead():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    event_past = {
        "wallet": "0x1", "side": "BUY", "usd_value": 100000,
        "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90,
    }
    event_future = {
        "wallet": "0x2", "side": "BUY", "usd_value": 200000,
        "timestamp": now + timedelta(minutes=30), "whale_score": 80, "smart_money_score": 80, "confidence": 90,
    }
    as_of = now + timedelta(minutes=10)
    consensus = engine.compute_consensus("ethereum", "0xtoken", [event_past, event_future], as_of=as_of)
    assert consensus is not None
    assert consensus.independent_buying_whales == 1
    assert consensus.total_buy_volume == 100000
