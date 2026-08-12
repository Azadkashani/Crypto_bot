def test_core_imports():
    """
    تست وارد شدن همه ماژول‌های اصلی بدون خطا.
    """
    try:
        import config
        import data
        import regime
        import indicators
        import strategy
        import backtest
        import main
        import metrics
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")

def test_datafetcher_instantiation_no_network(mocker):
    """
    اطمینان از اینکه می‌توان DataFetcher را بدون اتصال واقعی نمونه‌سازی کرد.
    """
    mocker.patch('ccxt.gate')
    from data import DataFetcher
    fetcher = DataFetcher()
    assert fetcher is not None
    assert hasattr(fetcher, 'exchange')
