# FILE: src/strategy/backtest/backtest_runner.py

"""
Backtest Runner — اجرای Pipeline روی داده OHLCV واقعی
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import csv
import os
from ..pipeline.strategy_pipeline import StrategyPipeline, StrategyPipelineConfig
from .backtest_engine import BacktestEngine
from .backtest_types import BacktestConfig, BacktestResult


@dataclass
class BacktestRunnerConfig:
    """پیکربندی Backtest Runner"""
    symbol: str = "BTC_USDT"
    timeframe: str = "1h"
    initial_equity: float = 10000.0
    pipeline_config: Optional[StrategyPipelineConfig] = None
    backtest_config: Optional[BacktestConfig] = None


class DataValidationError(Exception):
    """خطای اعتبارسنجی داده"""
    pass


class BacktestRunner:
    """
    اجراکننده Backtest روی داده OHLCV واقعی
    
    مسئولیت:
    - بارگذاری داده OHLCV
    - اعتبارسنجی داده
    - اجرای Pipeline کندل به کندل
    - ارسال نتایج به Backtest Engine
    """
    
    def __init__(self, config: Optional[BacktestRunnerConfig] = None):
        self.config = config or BacktestRunnerConfig()
        
        self.pipeline = StrategyPipeline(
            self.config.pipeline_config or StrategyPipelineConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                initial_equity=self.config.initial_equity
            )
        )
        
        self.backtest_engine = BacktestEngine(
            self.config.backtest_config or BacktestConfig(
                initial_equity=self.config.initial_equity
            )
        )
    
    def reset(self):
        """بازنشانی کامل Runner"""
        self.pipeline.reset()
        self.backtest_engine.reset()
    
    def run(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> BacktestResult:
        """
        اجرای Backtest روی داده OHLCV
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            symbol: نماد (اختیاری — از config استفاده می‌شود)
            timeframe: تایم‌فریم (اختیاری — از config استفاده می‌شود)
        
        Returns:
            BacktestResult
        """
        # بازنشانی
        self.reset()
        
        sym = symbol or self.config.symbol
        tf = timeframe or self.config.timeframe
        
        # اعتبارسنجی داده
        self._validate_ohlcv_data(ohlcv_data)
        
        # اجرای Pipeline کندل به کندل
        for current_index in range(2, len(ohlcv_data)):
            visible_ohlcv = ohlcv_data[:current_index + 1]
            
            # پردازش Pipeline
            pipeline_result = self.pipeline.process_candle(
                ohlcv_data=visible_ohlcv,
                current_index=current_index
            )
            
            # ارسال سیگنال‌های COMPLETE به Backtest
            for signal in pipeline_result.signals:
                if signal.status == "COMPLETE" and signal.execution_result is not None:
                    if signal.execution_result.order is not None:
                        # اتصال به Backtest Engine
                        self._submit_order_to_backtest(
                            order=signal.execution_result.order,
                            visible_ohlcv=visible_ohlcv,
                            current_index=current_index
                        )
        
        # ساخت نتیجه نهایی
        return self.backtest_engine._build_result()
    
    def run_from_csv(
        self,
        file_path: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> BacktestResult:
        """
        بارگذاری CSV و اجرای Backtest
        
        Args:
            file_path: مسیر فایل CSV
            symbol: نماد
            timeframe: تایم‌فریم
        
        Returns:
            BacktestResult
        """
        ohlcv_data = self.load_csv(file_path)
        return self.run(ohlcv_data, symbol, timeframe)
    
    def load_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """
        بارگذاری داده OHLCV از CSV
        
        فرمت CSV:
        timestamp,open,high,low,close,volume
        
        Args:
            file_path: مسیر فایل
        
        Returns:
            لیست کندل‌ها
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        data = []
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            if reader.fieldnames is None:
                raise DataValidationError("CSV has no headers")
            
            for col in required_columns:
                if col not in reader.fieldnames:
                    raise DataValidationError(f"Missing required column: {col}")
            
            for row in reader:
                try:
                    candle = {
                        'timestamp': int(row['timestamp']),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']),
                    }
                    data.append(candle)
                except (ValueError, KeyError) as e:
                    raise DataValidationError(f"Invalid data in CSV: {e}")
        
        return data
    
    def _validate_ohlcv_data(self, ohlcv_data: List[Dict[str, Any]]):
        """اعتبارسنجی کامل داده OHLCV"""
        if not ohlcv_data:
            raise DataValidationError("Empty OHLCV data")
        
        required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        for i, candle in enumerate(ohlcv_data):
            # بررسی فیلدهای ضروری
            for field in required_fields:
                if field not in candle:
                    raise DataValidationError(
                        f"Candle {i}: missing field '{field}'"
                    )
            
            # بررسی NaN
            for field in ['open', 'high', 'low', 'close', 'volume']:
                val = candle[field]
                if val is None or (isinstance(val, float) and val != val):  # NaN check
                    raise DataValidationError(
                        f"Candle {i}: NaN value in '{field}'"
                    )
            
            # بررسی مقادیر عددی
            for field in ['open', 'high', 'low', 'close', 'volume']:
                if not isinstance(candle[field], (int, float)):
                    raise DataValidationError(
                        f"Candle {i}: non-numeric value in '{field}'"
                    )
            
            # بررسی منطق OHLC
            if candle['high'] < candle['low']:
                raise DataValidationError(
                    f"Candle {i}: high ({candle['high']}) < low ({candle['low']})"
                )
            
            # بررسی timestamp
            if not isinstance(candle['timestamp'], (int, float)):
                raise DataValidationError(
                    f"Candle {i}: invalid timestamp type"
                )
            
            if candle['timestamp'] < 0:
                raise DataValidationError(
                    f"Candle {i}: negative timestamp"
                )
        
        # بررسی timestamps
        timestamps = [c['timestamp'] for c in ohlcv_data]
        
        # بررسی مرتب‌سازی
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                raise DataValidationError(
                    f"Unsorted timestamps at index {i}: "
                    f"{timestamps[i]} < {timestamps[i-1]}"
                )
        
        # بررسی تکراری
        if len(set(timestamps)) != len(timestamps):
            raise DataValidationError("Duplicate timestamps found")
    
    def _submit_order_to_backtest(
        self,
        order,
        visible_ohlcv: List[Dict[str, Any]],
        current_index: int
    ):
        """ارسال سفارش به Backtest Engine"""
        # این متد placeholder است
        # Backtest Engine فعلی به صورت مستقل PnL را محاسبه می‌کند
        # اتصال کامل در تست‌های یکپارچه انجام می‌شود
        pass
