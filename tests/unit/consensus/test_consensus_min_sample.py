import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine
from src.core.config import settings

def test_insufficient_sample():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        {"wallet": "0x1", "side": "BUY", "usd_value": 100000, "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90},
        {"wallet": "0x2", "side": "BUY", "usd_value": 150000, "timestamp": now + timedelta(minutes=5), "whale_score": 80, "smart_money_score": 80, "confidence": 90},
    ]
    original = settings.min_independent_whales
    settings.min_independent_whales = 3
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    settings.min_independent_whales = original
    assert consensus.status == "INSUFFICIENT_SAMPLE"
