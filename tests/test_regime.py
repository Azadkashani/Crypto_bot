from regime import get_regime

def test_get_regime_dummy():
    """
    تابع get_regime در حال حاضر همیشه bullish برمی‌گرداند.
    """
    result = get_regime(None, '4h')
    assert result == 'bullish'
