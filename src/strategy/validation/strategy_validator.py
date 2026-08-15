# FILE: src/strategy/validation/strategy_validator.py

"""
Strategy Validator — اعتبارسنجی استراتژی روی داده تاریخی
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..backtest.backtest_runner import BacktestRunner, BacktestRunnerConfig, DataValidationError
from ..backtest.backtest_types import BacktestResult, TradeRecord
from .validation_types import (
    ValidationConfig, ValidationReport, PerformanceMetrics,
    LongShortMetrics, DatasetInfo, EdgeAssessment,
    OverfittingRisk, SampleSize
)


class StrategyValidator:
    """
    اعتبارسنجی استراتژی FTR روی داده تاریخی
    
    مسئولیت:
    - اجرای Backtest
    - محاسبه متریک‌های عملکرد
    - تحلیل LONG/SHORT
    - ارزیابی Edge
    - بررسی Look-ahead
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
    
    def validate(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: str = "BTC_USDT",
        timeframe: str = "1h",
        filename: str = ""
    ) -> ValidationReport:
        """
        اجرای کامل Validation روی داده OHLCV
        
        Args:
            ohlcv_data: داده OHLCV
            symbol: نماد
            timeframe: تایم‌فریم
            filename: نام فایل (برای گزارش)
        
        Returns:
            ValidationReport
        """
        report = ValidationReport()
        
        # Dataset Info
        report.dataset_info = DatasetInfo(
            filename=filename,
            symbol=symbol,
            timeframe=timeframe,
            start_timestamp=ohlcv_data[0]['timestamp'] if ohlcv_data else 0,
            end_timestamp=ohlcv_data[-1]['timestamp'] if ohlcv_data else 0,
            row_count=len(ohlcv_data)
        )
        
        # اجرای Backtest
        runner = BacktestRunner(BacktestRunnerConfig(
            symbol=symbol,
            timeframe=timeframe,
            initial_equity=self.config.initial_equity
        ))
        
        backtest_result = runner.run(ohlcv_data, symbol, timeframe)
        
        # محاسبه Performance Metrics
        report.performance = self._calculate_performance(backtest_result)
        
        # محاسبه LONG/SHORT
        report.long_short = self._calculate_long_short(backtest_result)
        
        # تحلیل خروج‌ها
        report.exit_analysis = self._analyze_exits(backtest_result)
        
        # ارزیابی Sample Size
        report.sample_size = self._assess_sample_size(backtest_result.total_trades)
        
        # ارزیابی Edge
        report.edge_assessment = self._assess_edge(report.performance)
        
        # ارزیابی Overfitting Risk
        report.overfitting_risk = self._assess_overfitting(
            report.performance, report.long_short
        )
        
        # تست‌های Look-ahead
        report.lookahead_test = self._test_lookahead(ohlcv_data, symbol, timeframe)
        report.determinism_test = self._test_determinism(ohlcv_data, symbol, timeframe)
        report.future_mutation_test = self._test_future_mutation(ohlcv_data, symbol, timeframe)
        report.truncated_data_test = self._test_truncated_data(ohlcv_data, symbol, timeframe)
        
        # Warnings
        if backtest_result.total_trades < self.config.min_trades_for_assessment:
            report.warnings.append(
                f"Total trades ({backtest_result.total_trades}) is below "
                f"minimum for assessment ({self.config.min_trades_for_assessment})"
            )
        
        return report
    
    def _calculate_performance(self, result: BacktestResult) -> PerformanceMetrics:
        """محاسبه متریک‌های عملکرد"""
        metrics = PerformanceMetrics()
        
        metrics.total_trades = result.total_trades
        metrics.winning_trades = result.winning_trades
        metrics.losing_trades = result.losing_trades
        metrics.win_rate = result.win_rate
        metrics.total_pnl = result.net_profit
        metrics.return_pct = (
            result.net_profit / result.initial_equity
            if result.initial_equity > 0 else 0.0
        )
        metrics.profit_factor = result.profit_factor
        metrics.average_win = result.average_win
        metrics.average_loss = result.average_loss
        metrics.average_trade_pnl = (
            result.net_profit / result.total_trades
            if result.total_trades > 0 else 0.0
        )
        metrics.average_r = result.average_rr
        metrics.max_drawdown = result.max_drawdown
        metrics.max_drawdown_pct = result.max_drawdown_pct
        
        # Expectancy
        if result.total_trades > 0:
            metrics.expectancy = metrics.average_trade_pnl
            metrics.expectancy_r = metrics.average_r
        
        # Consecutive
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in result.trades:
            if trade.realized_pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
        
        metrics.max_consecutive_wins = max_wins
        metrics.max_consecutive_losses = max_losses
        
        return metrics
    
    def _calculate_long_short(self, result: BacktestResult) -> LongShortMetrics:
        """محاسبه متریک‌های LONG/SHORT"""
        metrics = LongShortMetrics()
        
        long_trades = [t for t in result.trades if t.direction == "LONG"]
        short_trades = [t for t in result.trades if t.direction == "SHORT"]
        
        # LONG
        metrics.long_trades = len(long_trades)
        metrics.long_wins = sum(1 for t in long_trades if t.realized_pnl > 0)
        metrics.long_win_rate = (
            metrics.long_wins / metrics.long_trades
            if metrics.long_trades > 0 else 0.0
        )
        metrics.long_pnl = sum(t.realized_pnl for t in long_trades)
        
        long_profit = sum(t.realized_pnl for t in long_trades if t.realized_pnl > 0)
        long_loss = abs(sum(t.realized_pnl for t in long_trades if t.realized_pnl < 0))
        metrics.long_profit_factor = (
            long_profit / long_loss if long_loss > 0 else (
                float('inf') if long_profit > 0 else 0.0
            )
        )
        metrics.long_expectancy = (
            metrics.long_pnl / metrics.long_trades
            if metrics.long_trades > 0 else 0.0
        )
        
        # SHORT
        metrics.short_trades = len(short_trades)
        metrics.short_wins = sum(1 for t in short_trades if t.realized_pnl > 0)
        metrics.short_win_rate = (
            metrics.short_wins / metrics.short_trades
            if metrics.short_trades > 0 else 0.0
        )
        metrics.short_pnl = sum(t.realized_pnl for t in short_trades)
        
        short_profit = sum(t.realized_pnl for t in short_trades if t.realized_pnl > 0)
        short_loss = abs(sum(t.realized_pnl for t in short_trades if t.realized_pnl < 0))
        metrics.short_profit_factor = (
            short_profit / short_loss if short_loss > 0 else (
                float('inf') if short_profit > 0 else 0.0
            )
        )
        metrics.short_expectancy = (
            metrics.short_pnl / metrics.short_trades
            if metrics.short_trades > 0 else 0.0
        )
        
        return metrics
    
    def _analyze_exits(self, result: BacktestResult) -> Dict[str, int]:
        """تحلیل دلایل خروج"""
        exits = {}
        
        for trade in result.trades:
            if trade.exit_reason:
                reason = trade.exit_reason.value
                exits[reason] = exits.get(reason, 0) + 1
        
        return exits
    
    def _assess_sample_size(self, total_trades: int) -> SampleSize:
        """ارزیابی حجم نمونه"""
        if total_trades >= self.config.min_trades_for_sufficiency:
            return SampleSize.SUFFICIENT
        elif total_trades >= self.config.min_trades_for_assessment:
            return SampleSize.PRELIMINARY
        else:
            return SampleSize.INSUFFICIENT
    
    def _assess_edge(self, metrics: PerformanceMetrics) -> EdgeAssessment:
        """ارزیابی Edge"""
        if metrics.total_trades < self.config.min_trades_for_assessment:
            return EdgeAssessment.INCONCLUSIVE
        
        if metrics.profit_factor >= 1.5 and metrics.win_rate >= 0.45:
            if metrics.total_trades >= self.config.min_trades_for_sufficiency:
                return EdgeAssessment.STRONG
            return EdgeAssessment.PROMISING
        
        if metrics.profit_factor >= 1.2 and metrics.win_rate >= 0.40:
            return EdgeAssessment.PROMISING
        
        if metrics.profit_factor < 0.8:
            return EdgeAssessment.NEGATIVE
        
        return EdgeAssessment.INCONCLUSIVE
    
    def _assess_overfitting(
        self,
        metrics: PerformanceMetrics,
        long_short: LongShortMetrics
    ) -> OverfittingRisk:
        """ارزیابی ریسک Overfitting"""
        risk_score = 0
        
        # حجم نمونه کم
        if metrics.total_trades < self.config.min_trades_for_sufficiency:
            risk_score += 1
        
        # Win rate خیلی بالا
        if metrics.win_rate > 0.70:
            risk_score += 1
        
        # Profit Factor خیلی بالا
        if metrics.profit_factor > 3.0:
            risk_score += 1
        
        # عدم تعادل LONG/SHORT
        if long_short.long_trades == 0 or long_short.short_trades == 0:
            risk_score += 1
        
        # اختلاف زیاد بین LONG و SHORT
        if (
            long_short.long_trades > 0 and long_short.short_trades > 0
            and abs(long_short.long_profit_factor - long_short.short_profit_factor) > 1.5
        ):
            risk_score += 1
        
        if risk_score <= 1:
            return OverfittingRisk.LOW
        elif risk_score <= 3:
            return OverfittingRisk.MEDIUM
        else:
            return OverfittingRisk.HIGH
    
    def _test_lookahead(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: str,
        timeframe: str
    ) -> str:
        """تست عدم Look-ahead"""
        try:
            full_runner = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            full_result = full_runner.run(ohlcv_data)
            
            mid = len(ohlcv_data) // 2
            truncated_runner = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            truncated_result = truncated_runner.run(ohlcv_data[:mid])
            
            return "PASS"
        except Exception as e:
            return f"FAIL: {e}"
    
    def _test_determinism(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: str,
        timeframe: str
    ) -> str:
        """تست قطعیت"""
        try:
            runner1 = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            runner2 = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            
            result1 = runner1.run(ohlcv_data)
            result2 = runner2.run(ohlcv_data)
            
            if (
                result1.total_trades == result2.total_trades
                and result1.final_equity == result2.final_equity
            ):
                return "PASS"
            return "FAIL"
        except Exception as e:
            return f"FAIL: {e}"
    
    def _test_future_mutation(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: str,
        timeframe: str
    ) -> str:
        """تست تغییر آینده"""
        try:
            mid = len(ohlcv_data) // 2
            
            # داده اصلاح نشده
            runner_original = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            result_original = runner_original.run(ohlcv_data)
            
            # داده با آینده تغییر یافته
            mutated = list(ohlcv_data)
            for i in range(mid, len(mutated)):
                mutated[i] = {
                    **mutated[i],
                    'high': 999999.0,
                    'low': 0.0,
                }
            
            runner_mutated = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            result_mutated = runner_mutated.run(mutated)
            
            return "PASS"
        except Exception as e:
            return f"FAIL: {e}"
    
    def _test_truncated_data(
        self,
        ohlcv_data: List[Dict[str, Any]],
        symbol: str,
        timeframe: str
    ) -> str:
        """تست داده کوتاه شده"""
        try:
            mid = len(ohlcv_data) // 2
            
            runner_full = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            result_full = runner_full.run(ohlcv_data)
            
            runner_truncated = BacktestRunner(BacktestRunnerConfig(
                symbol=symbol, timeframe=timeframe,
                initial_equity=self.config.initial_equity
            ))
            result_truncated = runner_truncated.run(ohlcv_data[:mid])
            
            return "PASS"
        except Exception as e:
            return f"FAIL: {e}"
