import config

def test_config_defaults():
    """
    اطمینان از وجود کلیدهای اصلی در کانفیگ.
    """
    assert hasattr(config, 'SYMBOL')
    assert hasattr(config, 'TIMEFRAMES')
    assert isinstance(config.RSI_OVERSOLD, int)
    assert isinstance(config.SCORE_THRESHOLD_LONG, int)
    assert '4h' in config.TIMEFRAMES
