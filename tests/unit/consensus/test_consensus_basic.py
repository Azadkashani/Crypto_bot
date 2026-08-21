import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def make_event(wallet, side, usd_value, timestamp, whale_score=80, smart_money_score=80, confidence=90):
    return {
        "wallet": wallet,
        "side": side,
        "usd_value": usd_value,
        "timestamp": timestamp,
        "whale_score": whale_score,
        "smart_money_score": smart_money_score,
        "confidence": confidence,
    }

def test_consensus_basic():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        make_event("0x1", "BUY", 100000, now),
        make_event("0x2", "BUY", 150000, now + timedelta(minutes=5)),
        make_event("0x3", "BUY", 200000, now + timedelta(minutes=10)),
    ]
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    assert consensus is not None
    assert consensus.direction == "BULLISH"
    assert consensus.independent_buying_whales == 3
    assert consensus.net_whale_flow > 0
    assert 0 <= consensus.consensus_score <= 100
