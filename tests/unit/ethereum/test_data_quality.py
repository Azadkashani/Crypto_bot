from src.data_quality.validator import DataQualityValidator

def test_validate_event():
    good_event = {"chain": "ethereum", "block_number": 1, "transaction_hash": "0x1", "timestamp": 123}
    bad_event = {"chain": "ethereum", "block_number": None, "transaction_hash": "0x1"}
    assert DataQualityValidator.validate_event(good_event) == True
    assert DataQualityValidator.validate_event(bad_event) == False
