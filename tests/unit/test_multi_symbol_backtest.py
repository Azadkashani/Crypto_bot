# FILE: tests/unit/test_multi_symbol_backtest.py

"""
تست‌های Multi-Symbol Backtest
"""

import pytest
from src.strategy.config.trading_universe import TradingUniverseConfig, MarginMode
from src.strategy.risk.position_constraints import PositionConstraintEngine


class TestMultiSymbolConstraints:
    """تست محدودیت‌های چند نماد"""
    
    def get_engine(self):
        return PositionConstraintEngine(TradingUniverseConfig())
    
    def test_12_symbols(self):
        config = TradingUniverseConfig()
        assert config.get_symbol_count() == 12
    
    def test_unknown_symbol(self):
        config = TradingUniverseConfig()
        assert not config.is_symbol_allowed("UNKNOWN_USDT")
    
    def test_volume_filter_pass(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=0, open_symbols=[]
        )
        assert result.is_valid
    
    def test_volume_filter_reject(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=500_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=0, open_symbols=[]
        )
        assert not result.is_valid
        assert any("Volume" in r for r in result.rejection_reasons)
    
    def test_4_positions_allowed(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="ADA_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=3,
            open_symbols=["BTC_USDT", "ETH_USDT", "SOL_USDT"]
        )
        assert result.is_valid
    
    def test_5th_position_rejected(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="ADA_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=4,
            open_symbols=["BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT"]
        )
        assert not result.is_valid
        assert any("Max open positions" in r for r in result.rejection_reasons)
    
    def test_duplicate_symbol(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="SHORT", entry_price=100, stop_loss=100.5,
            account_equity=1000, open_positions_count=1,
            open_symbols=["BTC_USDT"]
        )
        assert not result.is_valid
        assert any("already open" in r for r in result.rejection_reasons)
    
    def test_allocation_1000(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=0, open_symbols=[]
        )
        assert abs(result.position_margin - 250.0) < 0.01
    
    def test_allocation_10000(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=10000, open_positions_count=0, open_symbols=[]
        )
        assert abs(result.position_margin - 2500.0) < 0.01
    
    def test_risk_1000(self):
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=0, open_symbols=[]
        )
        assert abs(result.risk_amount - 10.0) < 0.01
    
    def test_leverage_05pct(self):
        engine = self.get_engine()
        _, lev = engine.calculate_leverage(100, 99.5, "LONG")
        assert abs(lev - 8.0) < 0.01
    
    def test_leverage_1pct(self):
        engine = self.get_engine()
        _, lev = engine.calculate_leverage(100, 99.0, "LONG")
        assert abs(lev - 4.0) < 0.01
    
    def test_leverage_2pct(self):
        engine = self.get_engine()
        _, lev = engine.calculate_leverage(100, 98.0, "LONG")
        assert abs(lev - 2.0) < 0.01
    
    def test_leverage_025pct(self):
        engine = self.get_engine()
        _, lev = engine.calculate_leverage(100, 99.75, "LONG")
        assert abs(lev - 16.0) < 0.01
    
    def test_isolated_margin(self):
        config = TradingUniverseConfig()
        assert config.margin_mode == MarginMode.ISOLATED
    
    def test_zero_equity(self):
        """تست equity صفر — باید رد شود"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=0, open_positions_count=0, open_symbols=[]
        )
        assert not result.is_valid
        assert any("Invalid account equity" in r for r in result.rejection_reasons)
    
    def test_negative_equity(self):
        """تست equity منفی — باید رد شود"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=-500, open_positions_count=0, open_symbols=[]
        )
        assert not result.is_valid
        assert any("Invalid account equity" in r for r in result.rejection_reasons)
    
    def test_positive_equity(self):
        """تست equity مثبت — باید معتبر باشد"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT", volume_usdt=5_000_000,
            direction="LONG", entry_price=100, stop_loss=99.5,
            account_equity=1000, open_positions_count=0, open_symbols=[]
        )
        assert result.is_valid
        assert result.position_margin > 0
        assert result.risk_amount > 0
