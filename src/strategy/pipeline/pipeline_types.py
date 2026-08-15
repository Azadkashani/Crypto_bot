# FILE: src/strategy/pipeline/pipeline_types.py

"""
تایپ‌های مخصوص Strategy Pipeline
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from ..signal.signal_quality_types import SignalQualityResult
from ..trade.trade_signal_types import TradeSignal
from ..risk.risk_types import RiskAssessment
from ..execution.execution_types import ExecutionResult


@dataclass
class PipelineSignal:
    """سیگنال کامل عبور کرده از Pipeline"""
    signal_id: str
    symbol: str
    direction: str
    signal_quality: Optional[SignalQualityResult] = None
    trade_signal: Optional[TradeSignal] = None
    risk_assessment: Optional[RiskAssessment] = None
    execution_result: Optional[ExecutionResult] = None
    status: str = "PENDING"  # PENDING, QUALIFIED, WATCH, REJECTED, RISK_REJECTED, EXECUTION_REJECTED, COMPLETE
    rejection_reasons: List[str] = field(default_factory=list)
    timestamp: int = 0


@dataclass
class PipelineResult:
    """نتیجه کامل اجرای Pipeline"""
    signals: List[PipelineSignal] = field(default_factory=list)
    total_processed: int = 0
    qualified_count: int = 0
    watch_count: int = 0
    rejected_count: int = 0
    trade_count: int = 0
    diagnostic_messages: List[str] = field(default_factory=list)
