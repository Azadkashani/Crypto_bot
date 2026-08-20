from src.core.config import Settings, Mode

def test_default_mode_research():
    s = Settings(_env_file=None)
    assert s.mode == Mode.research
    assert s.live_trading_enabled == False

def test_live_safety_gate():
    s = Settings(_env_file=None, mode="live", live_trading_enabled=False)
    assert s.live_trading_enabled == False
