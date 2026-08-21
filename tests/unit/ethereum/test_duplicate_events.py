from src.data_quality.deduplicator import Deduplicator

def test_deduplicate_events():
    dedup = Deduplicator()
    event1 = {"chain": "ethereum", "transaction_hash": "0x1", "log_index": 0}
    event2 = {"chain": "ethereum", "transaction_hash": "0x1", "log_index": 0}
    assert dedup.is_duplicate(event1) == False
    assert dedup.is_duplicate(event2) == True
