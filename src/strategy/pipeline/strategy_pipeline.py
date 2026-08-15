# FILE: src/strategy/pipeline/strategy_pipeline.py

"""
Strategy Pipeline — هماهنگ‌کننده تمام لایه‌های تصمیم‌گیری
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import StructureType, StructureBreak
from ..types.ftr_types import FTRZone, FTBEvent, FTRDetectionResult
from ..ftr.ftr_engine import FTREngine, FTREngineConfig
from ..signal.signal_quality_engine import SignalQualityEngine
from ..signal.signal_quality_types import SignalQualityResult, SignalClassification
from ..trade.trade_signal_engine import TradeSignalEngine
from ..trade.trade_signal_types import TradeSignal
from ..risk.risk_management_engine import RiskManagementEngine
from ..risk.risk_types import RiskAssessment, RiskConfig
from ..execution.execution_engine import ExecutionEngine, ExecutionConfig
from ..execution.execution_types import ExecutionResult
from .pipeline_types import PipelineResult, PipelineSignal


@dataclass
class StrategyPipelineConfig:
    """پیکربندی Strategy Pipeline"""
    symbol: str = "BTC_USDT"
    timeframe: str = "1h"
    initial_equity: float = 10000.0
    ftr_config: Optional[FTREngineConfig] = None
    signal_quality_engine: Optional[SignalQualityEngine] = None
    trade_signal_engine: Optional[TradeSignalEngine] = None
    risk_management_engine: Optional[RiskManagementEngine] = None
    execution_engine: Optional[ExecutionEngine] = None


class StrategyPipeline:
    """
    هماهنگ‌کننده تمام Pipeline
    
    مسئولیت: اتصال FTR → Signal Quality → Trade → Risk → Execution
    """
    
    def __init__(self, config: Optional[StrategyPipelineConfig] = None):
        self.config = config or StrategyPipelineConfig()
        
        # راه‌اندازی FTR Engine
        self.ftr_engine = FTREngine(
            self.config.ftr_config or FTREngineConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe
            )
        )
        
        # راه‌اندازی سایر Engines
        self.signal_quality_engine = self.config.signal_quality_engine or SignalQualityEngine()
        self.trade_signal_engine = self.config.trade_signal_engine or TradeSignalEngine()
        self.risk_management_engine = self.config.risk_management_engine or RiskManagementEngine()
        self.execution_engine = self.config.execution_engine or ExecutionEngine()
        
        self._equity = self.config.initial_equity
        self._processed_signals: set = set()
    
    def reset(self):
        """بازنشانی کامل Pipeline"""
        self.ftr_engine.reset()
        self.signal_quality_engine.reset()
        self.trade_signal_engine.reset()
        self.risk_management_engine.reset()
        self.execution_engine.reset()
        self._equity = self.config.initial_equity
        self._processed_signals.clear()
    
    def process_candle(
        self,
        ohlcv_data: List[dict],
        current_index: int
    ) -> PipelineResult:
        """
        پردازش یک کندل و اجرای کامل Pipeline
        
        Args:
            ohlcv_data: لیست کامل OHLCV
            current_index: ایندکس کندل جاری
        
        Returns:
            PipelineResult
        """
        result = PipelineResult()
        
        if current_index < 2:
            return result
        
        visible_ohlcv = ohlcv_data[:current_index + 1]
        current_timestamp = visible_ohlcv[current_index]['timestamp']
        
        # ۱. FTR Engine
        ftr_result = self.ftr_engine.process_bar(visible_ohlcv, current_index)
        
        # ۲. پردازش FTB Events
        for ftb_event in ftr_result.ftb_events:
            pipeline_signal = self._process_ftb(
                ftb_event=ftb_event,
                visible_ohlcv=visible_ohlcv,
                current_index=current_index,
                current_timestamp=current_timestamp
            )
            
            if pipeline_signal is not None:
                result.signals.append(pipeline_signal)
        
        result.total_processed = len(result.signals)
        result.qualified_count = sum(1 for s in result.signals if s.status == "COMPLETE")
        result.trade_count = sum(1 for s in result.signals if s.execution_result is not None and s.execution_result.success)
        
        return result
    
    def _process_ftb(
        self,
        ftb_event: FTBEvent,
        visible_ohlcv: List[dict],
        current_index: int,
        current_timestamp: int
    ) -> Optional[PipelineSignal]:
        """پردازش FTB Event از طریق تمام لایه‌ها"""
        zone = ftb_event.zone
        
        pipeline_signal = PipelineSignal(
            signal_id=f"SIG_{ftb_event.timestamp}_{zone.zone_id}",
            symbol=self.config.symbol,
            direction=zone.direction,
            timestamp=current_timestamp
        )
        
        # بررسی Duplicate
        if pipeline_signal.signal_id in self._processed_signals:
            pipeline_signal.status = "DUPLICATE"
            pipeline_signal.rejection_reasons.append("Duplicate signal")
            return pipeline_signal
        
        # ۲. Signal Quality
        structure_break = zone.structure_break
        if structure_break is None:
            pipeline_signal.status = "REJECTED"
            pipeline_signal.rejection_reasons.append("No structure break")
            return pipeline_signal
        
        market_structure_type = (
            StructureType.BULLISH if zone.direction == "LONG" else StructureType.BEARISH
        )
        
        signal_quality = self.signal_quality_engine.evaluate_signal(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            zone=zone,
            ftb_event=ftb_event,
            structure_break=structure_break,
            market_structure_type=market_structure_type,
            timestamp=current_timestamp,
            trend_direction=zone.direction
        )
        
        pipeline_signal.signal_quality = signal_quality
        
        # ۳. فیلتر classification
        if signal_quality.classification == SignalClassification.WATCH:
            pipeline_signal.status = "WATCH"
            pipeline_signal.rejection_reasons.append("Signal quality is WATCH")
            return pipeline_signal
        
        if signal_quality.classification == SignalClassification.REJECTED:
            pipeline_signal.status = "REJECTED"
            pipeline_signal.rejection_reasons.extend(signal_quality.rejection_reasons)
            return pipeline_signal
        
        # فقط QUALIFIED ادامه می‌دهد
        
        # ۴. Trade Signal
        structure_levels = self.ftr_engine.structure_analyzer.get_structure_levels()
        
        trade_signal = self.trade_signal_engine.create_trade_signal(
            signal_quality=signal_quality,
            zone=zone,
            ftb_event=ftb_event,
            structure_levels=structure_levels
        )
        
        if trade_signal is None or not trade_signal.is_valid:
            pipeline_signal.status = "REJECTED"
            pipeline_signal.rejection_reasons.append("Invalid trade signal")
            return pipeline_signal
        
        pipeline_signal.trade_signal = trade_signal
        
        # ۵. Risk Management
        risk_assessment = self.risk_management_engine.calculate_position_size(
            trade_signal=trade_signal,
            account_equity=self._equity
        )
        
        if not risk_assessment.is_valid:
            pipeline_signal.status = "RISK_REJECTED"
            pipeline_signal.rejection_reasons.extend(
                [r.value for r in risk_assessment.rejection_reasons]
            )
            return pipeline_signal
        
        pipeline_signal.risk_assessment = risk_assessment
        
        # ۶. Execution
        execution_result = self.execution_engine.create_order(risk_assessment)
        
        if not execution_result.success:
            pipeline_signal.status = "EXECUTION_REJECTED"
            pipeline_signal.rejection_reasons.extend(execution_result.errors)
            return pipeline_signal
        
        pipeline_signal.execution_result = execution_result
        pipeline_signal.status = "COMPLETE"
        
        # ثبت signal
        self._processed_signals.add(pipeline_signal.signal_id)
        
        return pipeline_signal
