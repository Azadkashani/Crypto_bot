import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def test_duplicate_wallet_dedup():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        {"wallet": "0x1", "side": "BUY", "usd_value": 100000, "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90},
        {"wallet": "0x1", "side": "BUY", "usd_value": 50000, "timestamp": now + timedelta(minutes=1), "whale_score": 80, "smart_money_score": 80, "confidence": 90},
    ]
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    assert consensus.independent_buying_whales == 1
