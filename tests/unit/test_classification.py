from src.classification.base import ClassificationResult

def test_classification_result():
    r = ClassificationResult(label="BUY", confidence=0.95)
    assert r.label == "BUY"
    assert r.confidence == 0.95
