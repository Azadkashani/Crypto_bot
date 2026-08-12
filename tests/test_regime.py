import pandas as pd
from regime import get_regime, REGIME_RANGE

def test_get_regime_dummy():
    """
    با دیتافریم خالی، باید RANGE برگرداند.
    """
    result = get_regime(pd.DataFrame())
    assert result == REGIME_RANGE
