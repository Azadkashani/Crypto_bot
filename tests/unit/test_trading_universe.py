# FILE: tests/unit/test_trading_universe.py

"""
تست‌های Trading Universe و Position Constraints
"""

import pytest
from src.strategy.config.trading_universe import (
    TradingUniverseConfig, VolumeFilter, MarginMode
)
from src.strategy.risk.position_constraints import (
    PositionConstraintEngine, LeverageConfig
)


class TestTradingUniverse:
    """تست Universe معاملاتی"""
    
    def test_exactly_12_symbols(self):
        """تست ۱۲ نماد"""
        config = TradingUniverseConfig()
        
        assert config.get_symbol_count() == 12
    
    def test_no_duplicates(self):
        """تست عدم وجود تکراری"""
        config = TradingUniverseConfig()
        
        assert len(set(config.symbols)) == 12
    
    def test_unknown_symbol_rejected(self):
        """تست نماد نامعتبر"""
        config = TradingUniverseConfig()
        
        assert not config.is_symbol_allowed("BTC_USDT_XYZ")
        assert config.is_symbol_allowed("BTC_USDT")
    
    def test_validation_pass(self):
        """تست پیکربندی معتبر"""
        config = TradingUniverseConfig()
        errors = config.validate()
        
        assert len(errors) == 0
    
    def test_position_risk_fraction(self):
        """تست ریسک نسبی پوزیشن"""
        config = TradingUniverseConfig()
        
        assert config.position_equity_fraction == 0.25
        assert config.risk_per_trade == 0.01
        assert abs(config.position_risk_fraction - 0.04) < 0.0001


class TestVolumeFilter:
    """تست فیلتر حجم"""
    
    def test_volume_above_min(self):
        """تست حجم بالاتر از حداقل"""
        filter_ = VolumeFilter(1_000_000.0)
        result = filter_.check("BTC_USDT", 5_000_000.0)
        
        assert result.is_eligible
    
    def test_volume_below_min(self):
        """تست حجم پایین‌تر از حداقل"""
        filter_ = VolumeFilter(1_000_000.0)
        result = filter_.check("BTC_USDT", 500_000.0)
        
        assert not result.is_eligible
        assert result.reason is not None
    
    def test_volume_exactly_min(self):
        """تست حجم دقیقاً برابر حداقل"""
        filter_ = VolumeFilter(1_000_000.0)
        result = filter_.check("BTC_USDT", 1_000_000.0)
        
        assert result.is_eligible


class TestPositionConstraints:
    """تست محدودیت‌های پوزیشن"""
    
    def get_engine(self) -> PositionConstraintEngine:
        return PositionConstraintEngine(
            universe_config=TradingUniverseConfig(),
            leverage_config=LeverageConfig(max_exchange_leverage=100.0)
        )
    
    def test_leverage_calculation_05pct(self):
        """تست اهرم با SL=0.5%"""
        engine = self.get_engine()
        
        stop_pct, leverage = engine.calculate_leverage(100.0, 99.5, "LONG")
        
        assert abs(stop_pct - 0.005) < 0.0001
        assert abs(leverage - 8.0) < 0.01
    
    def test_leverage_calculation_1pct(self):
        """تست اهرم با SL=1%"""
        engine = self.get_engine()
        
        stop_pct, leverage = engine.calculate_leverage(100.0, 99.0, "LONG")
        
        assert abs(stop_pct - 0.01) < 0.0001
        assert abs(leverage - 4.0) < 0.01
    
    def test_leverage_calculation_2pct(self):
        """تست اهرم با SL=2%"""
        engine = self.get_engine()
        
        stop_pct, leverage = engine.calculate_leverage(100.0, 98.0, "LONG")
        
        assert abs(stop_pct - 0.02) < 0.0001
        assert abs(leverage - 2.0) < 0.01
    
    def test_leverage_calculation_4pct(self):
        """تست اهرم با SL=4%"""
        engine = self.get_engine()
        
        stop_pct, leverage = engine.calculate_leverage(100.0, 96.0, "LONG")
        
        assert abs(stop_pct - 0.04) < 0.0001
        assert abs(leverage - 1.0) < 0.01
    
    def test_leverage_calculation_025pct(self):
        """تست اهرم با SL=0.25%"""
        engine = self.get_engine()
        
        stop_pct, leverage = engine.calculate_leverage(100.0, 99.75, "LONG")
        
        assert abs(stop_pct - 0.0025) < 0.0001
        assert abs(leverage - 16.0) < 0.01
    
    def test_zero_stop_distance_rejected(self):
        """تست فاصله صفر"""
        engine = self.get_engine()
        
        with pytest.raises(ValueError):
            engine.calculate_leverage(100.0, 100.0, "LONG")
    
    def test_negative_stop_distance_rejected(self):
        """تست فاصله منفی"""
        engine = self.get_engine()
        
        with pytest.raises(ValueError):
            engine.calculate_leverage(100.0, 105.0, "LONG")
    
    def test_position_allocation(self):
        """تست تخصیص سرمایه"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=5_000_000.0,
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,
            account_equity=1000.0,
            open_positions_count=0,
            open_symbols=[]
        )
        
        assert result.is_valid
        assert abs(result.position_margin - 250.0) < 0.01
        assert abs(result.risk_amount - 10.0) < 0.01
        assert abs(result.required_leverage - 8.0) < 0.01
    
    def test_max_positions_reached(self):
        """تست حداکثر پوزیشن"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=5_000_000.0,
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,
            account_equity=1000.0,
            open_positions_count=4,
            open_symbols=["ETH_USDT", "SOL_USDT", "XRP_USDT", "BNB_USDT"]
        )
        
        assert not result.is_valid
        assert any("Max open positions" in r for r in result.rejection_reasons)
    
    def test_duplicate_symbol_rejected(self):
        """تست نماد تکراری"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=5_000_000.0,
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,
            account_equity=1000.0,
            open_positions_count=1,
            open_symbols=["BTC_USDT"]
        )
        
        assert not result.is_valid
        assert any("Position already open" in r for r in result.rejection_reasons)
    
    def test_isolated_margin_required(self):
        """تست مارجین ایزوله"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=5_000_000.0,
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,
            account_equity=1000.0,
            open_positions_count=0,
            open_symbols=[],
            margin_mode=MarginMode.CROSS
        )
        
        assert not result.is_valid
        assert any("ISOLATED" in r for r in result.rejection_reasons)
    
    def test_exchange_max_leverage(self):
        """تست سقف اهرم صرافی"""
        engine = PositionConstraintEngine(
            universe_config=TradingUniverseConfig(),
            leverage_config=LeverageConfig(max_exchange_leverage=5.0)
        )
        
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=5_000_000.0,
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,  # SL=0.5% → اهرم 8x > max 5x
            account_equity=1000.0,
            open_positions_count=0,
            open_symbols=[]
        )
        
        assert not result.is_valid
        assert any("exceeds max" in r for r in result.rejection_reasons)
    
    def test_volume_filter_integration(self):
        """تست فیلتر حجم در Position Constraints"""
        engine = self.get_engine()
        result = engine.validate_position(
            symbol="BTC_USDT",
            volume_usdt=500_000.0,  # کمتر از 1M
            direction="LONG",
            entry_price=100.0,
            stop_loss=99.5,
            account_equity=1000.0,
            open_positions_count=0,
            open_symbols=[]
        )
        
        assert not result.is_valid
        assert any("Volume" in r for r in result.rejection_reasons)
