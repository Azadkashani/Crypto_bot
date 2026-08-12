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

def test_fetcher_singleton():
    """data.fetcher یک نمونه از DataFetcher است."""
    from data import fetcher
    assert fetcher is not None
