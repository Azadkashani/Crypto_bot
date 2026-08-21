from src.core.config import settings

def test_confirmation_blocks_config():
    assert settings.eth_confirmation_blocks > 0
    assert settings.eth_finality_blocks > 0
