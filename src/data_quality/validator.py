class DataQualityValidator:
    @staticmethod
    def validate_event(event: dict) -> bool:
        required = ["chain", "block_number", "transaction_hash", "timestamp"]
        return all(field in event for field in required)

    @staticmethod
    def validate_classification(classification: dict) -> bool:
        if "label" not in classification or "confidence" not in classification:
            return False
        if classification["confidence"] < 0 or classification["confidence"] > 1:
            return False
        return True
