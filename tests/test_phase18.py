def test_timestamp_validation_non_utc():
    df = pd.DataFrame({'open':[100], 'high':[101], 'low':[99], 'close':[100], 'volume':[10]},
                      index=pd.DatetimeIndex([pd.Timestamp('2025-01-01')]))
    res = validate_ohlcv(df, '5m')
    # ایندکس timezone ندارد، validate_ohlcv باید بدون خطا اجرا شود
    assert df.index.tz is None
    assert res['valid'] is True  # چون timezone بررسی نمی‌شود


def test_warmup_data_before_backtest_start():
    backtest_start = pd.Timestamp('2025-02-01', tz='UTC')
    warmup_start = pd.Timestamp('2025-01-01', tz='UTC')
    assert warmup_start < backtest_start
    df_warmup = _make_df('2025-01-01 00:00:00', 100, '1h')
    df_test = _make_df('2025-02-01 00:00:00', 100, '1h')
    full = pd.concat([df_warmup, df_test])
    # چون بازه موردنظر از backtest_start شروع می‌شود، فقط داده test بررسی می‌شود
    res = validate_coverage(full, '1h', backtest_start, backtest_start + timedelta(days=4))
    assert res['coverage_ok'] is True
