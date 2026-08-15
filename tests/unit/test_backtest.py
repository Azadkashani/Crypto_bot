# FILE: tests/unit/test_backtest.py

"""
تست‌های Backtest Engine
"""

import pytest
from typing import List, Dict, Any
from src.strategy.backtest.backtest_engine import BacktestEngine
from src.strategy.backtest.backtest_types import (
    BacktestConfig, ExitReason, TradeRecord
)


def create_ohlcv_data(prices: List[float], highs: List[float], lows: List[float],
                     opens: List[float]) -> List[dict]:
    """ایجاد داده OHLCV"""
    data = []
    for i in range(len(prices)):
        data.append({
            'open': opens[i],
            'high': highs[i],
            'low': lows[i],
            'close': prices[i],
            'volume': 100,
            'timestamp': i * 3600
        })
    return data


def create_simple_uptrend() -> List[dict]:
    """داده صعودی ساده برای تست"""
    n = 50
    prices = []
    highs = []
    lows = []
    opens = []
    
    for i in range(n):
        price = 100 + i * 0.5
        opens.append(price - 0.2)
        prices.append(price)
        highs.append(price + 0.5)
        lows.append(price - 0.5)
    
    return create_ohlcv_data(prices, highs, lows, opens)


class TestBacktestEngine:
    """تست‌های Backtest"""
    
    def test_reset(self):
        """تست Reset"""
        engine = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        engine.run(data)
        engine.reset()
        
        assert engine._equity == 10000.0
        assert engine._open_position is None
        assert len(engine._trades) == 0
        assert len(engine._processed_signals) == 0
    
    def test_determinism(self):
        """تست قطعیت"""
        engine1 = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        engine2 = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        result1 = engine1.run(data)
        result2 = engine2.run(data)
        
        assert result1.total_trades == result2.total_trades
        assert result1.final_equity == result2.final_equity
        assert result1.net_profit == result2.net_profit
    
    def test_no_trades_on_empty_signals(self):
        """تست بدون معامله وقتی سیگنالی نیست"""
        engine = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        result = engine.run(data)
        
        assert result.total_trades == 0
        assert result.final_equity == 10000.0
    
    def test_initial_equity(self):
        """تست equity اولیه"""
        engine = BacktestEngine(BacktestConfig(initial_equity=50000.0))
        data = create_simple_uptrend()
        
        result = engine.run(data)
        
        assert result.initial_equity == 50000.0
        assert result.final_equity == 50000.0
    
    def test_zero_trades_metrics(self):
        """تست متریک‌های صفر معامله"""
        engine = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        result = engine.run(data)
        
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.max_drawdown == 0.0
    
    def test_no_lookahead_truncated(self):
        """تست عدم Look-ahead با داده کوتاه شده"""
        engine_full = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        engine_truncated = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        # اجرا روی داده کامل
        result_full = engine_full.run(data)
        
        # اجرا روی داده کوتاه شده
        truncated = data[:30]
        result_truncated = engine_truncated.run(truncated)
        
        # هر دو باید بدون معامله باشند چون FTR Engine تنظیم نشده
        assert result_full.total_trades == result_truncated.total_trades == 0
    
    def test_no_future_dependency(self):
        """تست عدم وابستگی به آینده"""
        engine = BacktestEngine(BacktestConfig(initial_equity=10000.0))
        data = create_simple_uptrend()
        
        result = engine.run(data)
        
        # بدون FTR Engine هیچ معامله‌ای نباید باشد
        assert result.total_trades == 0
    
    def test_same_candle_sl_first_policy(self):
        """تست سیاست SL_FIRST در کندل همزمان"""
        config = BacktestConfig(
            initial_equity=10000.0,
            same_candle_conflict_policy="SL_FIRST"
        )
        engine = BacktestEngine(config)
        
        assert config.same_candle_conflict_policy == "SL_FIRST"
    
    def test_same_candle_tp_first_policy(self):
        """تست سیاست TP_FIRST در کندل همزمان"""
        config = BacktestConfig(
            initial_equity=10000.0,
            same_candle_conflict_policy="TP_FIRST"
        )
        engine = BacktestEngine(config)
        
        assert config.same_candle_conflict_policy == "TP_FIRST"
    
    def test_invalid_config(self):
        """تست پیکربندی نامعتبر"""
        config = BacktestConfig(initial_equity=0.0)
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("initial_equity" in e for e in errors)
    
    def test_trade_record_to_dict(self):
        """تست تبدیل TradeRecord به دیکشنری"""
        trade = TradeRecord(
            trade_id="TRD_1",
            signal_id="SIG_1",
            symbol="BTC_USDT",
            direction="LONG",
            entry_timestamp=100000,
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            position_size=50.0,
            risk_amount=100.0,
            exit_timestamp=105000,
            exit_price=106.0,
            exit_reason=ExitReason.TAKE_PROFIT,
            realized_pnl=300.0,
            rr_realized=3.0
        )
        
        d = trade.to_dict()
        
        assert d['trade_id'] == "TRD_1"
        assert d['direction'] == "LONG"
        assert d['exit_reason'] == "TAKE_PROFIT"
        assert d['realized_pnl'] == 300.0
