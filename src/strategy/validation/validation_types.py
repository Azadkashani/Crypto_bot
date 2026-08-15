# FILE: src/strategy/validation/validation_types.py

"""
تایپ‌های مخصوص Strategy Validation
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class EdgeAssessment(Enum):
    """ارزیابی Edge استراتژی"""
    STRONG = "STRONG"
    PROMISING = "PROMISING"
    INCONCLUSIVE = "INCONCLUSIVE"
    NEGATIVE = "NEGATIVE"


class OverfittingRisk(Enum):
    """ریسک Overfitting"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SampleSize(Enum):
    """وضعیت حجم نمونه"""
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    PRELIMINARY = "PRELIMINARY"


@dataclass
class DatasetInfo:
    """اطلاعات Dataset"""
    filename: str = ""
    symbol: str = ""
    timeframe: str = ""
    start_timestamp: int = 0
    end_timestamp: int = 0
    row_count: int = 0
    checksum: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """متریک‌های عملکرد"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    return_pct: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    average_trade_pnl: float = 0.0
    average_r: float = 0.0
    expectancy: float = 0.0
    expectancy_r: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'return_pct': self.return_pct,
            'profit_factor': self.profit_factor,
            'average_win': self.average_win,
            'average_loss': self.average_loss,
            'average_trade_pnl': self.average_trade_pnl,
            'average_r': self.average_r,
            'expectancy': self.expectancy,
            'expectancy_r': self.expectancy_r,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
        }


@dataclass
class LongShortMetrics:
    """متریک‌های جداگانه LONG و SHORT"""
    long_trades: int = 0
    long_wins: int = 0
    long_win_rate: float = 0.0
    long_pnl: float = 0.0
    long_profit_factor: float = 0.0
    long_expectancy: float = 0.0
    
    short_trades: int = 0
    short_wins: int = 0
    short_win_rate: float = 0.0
    short_pnl: float = 0.0
    short_profit_factor: float = 0.0
    short_expectancy: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'long': {
                'trades': self.long_trades,
                'wins': self.long_wins,
                'win_rate': self.long_win_rate,
                'pnl': self.long_pnl,
                'profit_factor': self.long_profit_factor,
                'expectancy': self.long_expectancy,
            },
            'short': {
                'trades': self.short_trades,
                'wins': self.short_wins,
                'win_rate': self.short_win_rate,
                'pnl': self.short_pnl,
                'profit_factor': self.short_profit_factor,
                'expectancy': self.short_expectancy,
            },
        }


@dataclass
class ValidationConfig:
    """پیکربندی Validation"""
    min_trades_for_assessment: int = 30
    min_trades_for_sufficiency: int = 100
    symbol: str = "BTC_USDT"
    timeframe: str = "1h"
    initial_equity: float = 10000.0
    
    def validate(self) -> List[str]:
        errors = []
        if self.min_trades_for_assessment <= 0:
            errors.append("min_trades_for_assessment must be > 0")
        if self.min_trades_for_sufficiency < self.min_trades_for_assessment:
            errors.append("min_trades_for_sufficiency must be >= min_trades_for_assessment")
        if self.initial_equity <= 0:
            errors.append("initial_equity must be > 0")
        return errors


@dataclass
class ValidationReport:
    """گزارش کامل Validation"""
    dataset_info: DatasetInfo = field(default_factory=DatasetInfo)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    long_short: LongShortMetrics = field(default_factory=LongShortMetrics)
    edge_assessment: EdgeAssessment = EdgeAssessment.INCONCLUSIVE
    overfitting_risk: OverfittingRisk = OverfittingRisk.MEDIUM
    sample_size: SampleSize = SampleSize.PRELIMINARY
    exit_analysis: Dict[str, int] = field(default_factory=dict)
    signal_quality_analysis: Dict[str, Dict[str, float]] = field(default_factory=dict)
    lookahead_test: str = "NOT_RUN"
    determinism_test: str = "NOT_RUN"
    future_mutation_test: str = "NOT_RUN"
    truncated_data_test: str = "NOT_RUN"
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'dataset_info': {
                'filename': self.dataset_info.filename,
                'symbol': self.dataset_info.symbol,
                'timeframe': self.dataset_info.timeframe,
                'start_timestamp': self.dataset_info.start_timestamp,
                'end_timestamp': self.dataset_info.end_timestamp,
                'row_count': self.dataset_info.row_count,
            },
            'performance': self.performance.to_dict(),
            'long_short': self.long_short.to_dict(),
            'edge_assessment': self.edge_assessment.value,
            'overfitting_risk': self.overfitting_risk.value,
            'sample_size': self.sample_size.value,
            'exit_analysis': self.exit_analysis,
            'signal_quality_analysis': self.signal_quality_analysis,
            'lookahead_test': self.lookahead_test,
            'determinism_test': self.determinism_test,
            'future_mutation_test': self.future_mutation_test,
            'truncated_data_test': self.truncated_data_test,
            'warnings': self.warnings,
        }
    
    def generate_text_report(self) -> str:
        """تولید گزارش متنی"""
        lines = []
        lines.append("=" * 50)
        lines.append("FTR STRATEGY VALIDATION REPORT")
        lines.append("=" * 50)
        lines.append(f"SYMBOL: {self.dataset_info.symbol}")
        lines.append(f"TIMEFRAME: {self.dataset_info.timeframe}")
        lines.append(f"ROWS: {self.dataset_info.row_count}")
        lines.append(f"TRADES: {self.performance.total_trades}")
        lines.append(f"WIN RATE: {self.performance.win_rate:.2%}")
        lines.append(f"PROFIT FACTOR: {self.performance.profit_factor:.2f}")
        lines.append(f"EXPECTANCY: {self.performance.expectancy:.4f}")
        lines.append(f"RETURN: {self.performance.return_pct:.2%}")
        lines.append(f"MAX DRAWDOWN: {self.performance.max_drawdown_pct:.2%}")
        lines.append("")
        lines.append(f"LONG TRADES: {self.long_short.long_trades}")
        lines.append(f"LONG WIN RATE: {self.long_short.long_win_rate:.2%}")
        lines.append(f"LONG PF: {self.long_short.long_profit_factor:.2f}")
        lines.append(f"SHORT TRADES: {self.long_short.short_trades}")
        lines.append(f"SHORT WIN RATE: {self.long_short.short_win_rate:.2%}")
        lines.append(f"SHORT PF: {self.long_short.short_profit_factor:.2f}")
        lines.append("")
        lines.append(f"EDGE: {self.edge_assessment.value}")
        lines.append(f"SAMPLE SIZE: {self.sample_size.value}")
        lines.append(f"OVERFITTING RISK: {self.overfitting_risk.value}")
        lines.append(f"LOOKAHEAD: {self.lookahead_test}")
        lines.append(f"DETERMINISM: {self.determinism_test}")
        lines.append(f"FUTURE MUTATION: {self.future_mutation_test}")
        lines.append(f"TRUNCATED DATA: {self.truncated_data_test}")
        lines.append("=" * 50)
        
        return "\n".join(lines)
