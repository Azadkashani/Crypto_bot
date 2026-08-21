from src.core.config import settings

def test_weights_sum_to_one():
    assert settings.validate_signal_weights() == True
