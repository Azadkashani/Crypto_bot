from src.data_quality.deduplicator import Deduplicator

def test_dedup():
    dedup = Deduplicator()
    e1 = {"chain": "ethereum", "transaction_hash": "0x1", "log_index": 0}
    e2 = {"chain": "ethereum", "transaction_hash": "0x1", "log_index": 0}
    assert dedup.is_duplicate(e1) == False
    assert dedup.is_duplicate(e2) == True
