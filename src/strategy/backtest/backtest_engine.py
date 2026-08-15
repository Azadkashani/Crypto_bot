# FILE: src/strategy/backtest/backtest_engine.py

"""
Backtest Engine — شبیه‌سازی تاریخی رویداد-محور
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from ..types.market_structure import StructureType
from ..types.ftr_types import FTRZone, FTBEvent, FTRZoneState
from ..signal.signal_quality_engine import SignalQualityEngine
from ..signal.signal_quality_types import SignalQualityResult, SignalClassification
from ..trade.trade_signal_engine import TradeSignalEngine
from ..trade.trade_signal_types import TradeSignal
from ..risk.risk_management_engine import RiskManagementEngine
from ..risk.risk_types import RiskAssessment, RiskConfig
from ..execution.execution_engine import ExecutionEngine, ExecutionConfig
from ..execution.execution_types import ExecutionResult
from .backtest_types import (
    BacktestConfig, BacktestResult, TradeRecord,
    PositionState, ExitReason
)


class BacktestEngine:
    """
    موتور شبیه‌سازی تاریخی
    
    این کلاس تمام Pipeline را به صورت رویداد-محور اجرا می‌کند:
    Candle → FTR → FTB → Quality → Trade → Risk → Execution → Position → PnL
    """
    
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        signal_quality_engine: Optional[SignalQualityEngine] = None,
        trade_signal_engine: Optional[TradeSignalEngine] = None,
        risk_management_engine: Optional[RiskManagementEngine] = None,
        execution_engine: Optional[ExecutionEngine] = None
    ):
        self.config = config or BacktestConfig()
        self.signal_quality_engine = signal_quality_engine or SignalQualityEngine()
        self.trade_signal_engine = trade_signal_engine or TradeSignalEngine()
        self.risk_management_engine = risk_management_engine or RiskManagementEngine()
        self.execution_engine = execution_engine or ExecutionEngine()
        
        self._ftr_engine = None  # باید توسط caller تنظیم شود
        self._equity = self.config.initial_equity
        self._peak_equity = self.config.initial_equity
        self._max_drawdown = 0.0
        self._open_position: Optional[PositionState] = None
        self._trades: List[TradeRecord] = []
        self._processed_signals: set = set()
        self._trade_counter = 0
    
    def reset(self):
        """بازنشانی کامل موتور"""
        self._equity = self.config.initial_equity
        self._peak_equity = self.config.initial_equity
        self._max_drawdown = 0.0
        self._open_position = None
        self._trades.clear()
        self._processed_signals.clear()
        self._trade_counter = 0
        self.signal_quality_engine.reset()
        self.trade_signal_engine.reset()
        self.risk_management_engine.reset()
        self.execution_engine.reset()
    
    def set_ftr_engine(self, ftr_engine):
        """تنظیم FTR Engine"""
        self._ftr_engine = ftr_engine
        self._ftr_engine.reset()
    
    def run(self, ohlcv_data: List[dict], symbol: str = "BTC_USDT",
            timeframe: str = "1h") -> BacktestResult:
        """
        اجرای Backtest روی داده OHLCV
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            symbol: نماد معاملاتی
            timeframe: تایم‌فریم
        
        Returns:
            BacktestResult
        """
        self.reset()
        
        for current_index in range(2, len(ohlcv_data)):
            visible_ohlcv = ohlcv_data[:current_index + 1]
            
            # ۱. پردازش FTR Engine
            if self._ftr_engine is not None:
                ftr_result = self._ftr_engine.process_bar(visible_ohlcv, current_index)
                
                # ۲. بررسی FTB Events
                for ftb_event in ftr_result.ftb_events:
                    self._process_ftb_event(
                        ftb_event=ftb_event,
                        visible_ohlcv=visible_ohlcv,
                        current_index=current_index,
                        symbol=symbol,
                        timeframe=timeframe
                    )
            
            # ۳. بررسی پوزیشن باز
            if self._open_position is not None:
                self._check_position_exit(visible_ohlcv, current_index)
        
        # بستن پوزیشن باز در انتهای داده
        if self._open_position is not None:
            last_candle = ohlcv_data[-1]
            self._close_position(
                position=self._open_position,
                exit_price=last_candle['close'],
                exit_timestamp=last_candle['timestamp'],
                exit_reason=ExitReason.END_OF_DATA
            )
        
        return self._build_result()
    
    def _process_ftb_event(
        self,
        ftb_event: FTBEvent,
        visible_ohlcv: List[dict],
        current_index: int,
        symbol: str,
        timeframe: str
    ):
        """پردازش FTB Event و ادامه Pipeline"""
        # اگر پوزیشن باز داریم و اجازه چند پوزیشن نداریم
        if (
            self._open_position is not None
            and not self.config.allow_multiple_positions
        ):
            return
        
        zone = ftb_event.zone
        
        # ساخت Structure Break (از metadata zone)
        structure_break = zone.structure_break
        if structure_break is None:
            return
        
        # ساختار بازار
        market_structure_type = StructureType.BULLISH if zone.direction == "LONG" else StructureType.BEARISH
        
        # ۱. Signal Quality
        signal_quality = self.signal_quality_engine.evaluate_signal(
            symbol=symbol,
            timeframe=timeframe,
            zone=zone,
            ftb_event=ftb_event,
            structure_break=structure_break,
            market_structure_type=market_structure_type,
            timestamp=visible_ohlcv[current_index]['timestamp'],
            trend_direction=zone.direction
        )
        
        # فقط QUALIFIED
        if signal_quality.classification != SignalClassification.QUALIFIED:
            return
        
        # ۲. Trade Signal
        structure_levels = self._ftr_engine.structure_analyzer.get_structure_levels() if self._ftr_engine else []
        trade_signal = self.trade_signal_engine.create_trade_signal(
            signal_quality=signal_quality,
            zone=zone,
            ftb_event=ftb_event,
            structure_levels=structure_levels
        )
        
        if trade_signal is None or not trade_signal.is_valid:
            return
        
        # جلوگیری از Duplicate
        if trade_signal.signal_id in self._processed_signals:
            return
        
        # ۳. Risk Management
        risk_assessment = self.risk_management_engine.calculate_position_size(
            trade_signal=trade_signal,
            account_equity=self._equity
        )
        
        if not risk_assessment.is_valid:
            return
        
        # ۴. Execution
        execution_result = self.execution_engine.create_order(risk_assessment)
        
        if not execution_result.success or execution_result.order is None:
            return
        
        # ۵. ثبت Signal
        self._processed_signals.add(trade_signal.signal_id)
        
        # ۶. ایجاد پوزیشن (Entry در کندل بعدی)
        if current_index + 1 >= len(visible_ohlcv):
            return
        
        self._trade_counter += 1
        position = PositionState(
            position_id=f"POS_{self._trade_counter}",
            signal_id=trade_signal.signal_id,
            symbol=symbol,
            direction=trade_signal.direction,
            entry_price=trade_signal.entry_price,
            stop_loss=trade_signal.stop_loss,
            take_profit=trade_signal.take_profit,
            position_size=risk_assessment.position_size,
            notional=risk_assessment.notional_value,
            risk_amount=risk_assessment.risk_amount,
            entry_timestamp=visible_ohlcv[current_index + 1]['timestamp'],
            entry_index=current_index + 1
        )
        
        self._open_position = position
    
    def _check_position_exit(self, ohlcv_data: List[dict], current_index: int):
        """بررسی خروج از پوزیشن"""
        if self._open_position is None:
            return
        
        position = self._open_position
        candle = ohlcv_data[current_index]
        
        # جلوگیری از بررسی همان کندل ورود
        if current_index <= position.entry_index:
            return
        
        sl_hit = False
        tp_hit = False
        
        if position.direction == "LONG":
            sl_hit = candle['low'] <= position.stop_loss
            tp_hit = candle['high'] >= position.take_profit
        else:  # SHORT
            sl_hit = candle['high'] >= position.stop_loss
            tp_hit = candle['low'] <= position.take_profit
        
        # هر دو همزمان
        if sl_hit and tp_hit:
            if self.config.same_candle_conflict_policy == "SL_FIRST":
                self._close_position(
                    position=position,
                    exit_price=position.stop_loss,
                    exit_timestamp=candle['timestamp'],
                    exit_reason=ExitReason.STOP_LOSS
                )
            else:
                self._close_position(
                    position=position,
                    exit_price=position.take_profit,
                    exit_timestamp=candle['timestamp'],
                    exit_reason=ExitReason.TAKE_PROFIT
                )
        elif sl_hit:
            self._close_position(
                position=position,
                exit_price=position.stop_loss,
                exit_timestamp=candle['timestamp'],
                exit_reason=ExitReason.STOP_LOSS
            )
        elif tp_hit:
            self._close_position(
                position=position,
                exit_price=position.take_profit,
                exit_timestamp=candle['timestamp'],
                exit_reason=ExitReason.TAKE_PROFIT
            )
    
    def _close_position(
        self,
        position: PositionState,
        exit_price: float,
        exit_timestamp: int,
        exit_reason: ExitReason
    ):
        """بستن پوزیشن و ثبت معامله"""
        # محاسبه PnL
        if position.direction == "LONG":
            pnl = (exit_price - position.entry_price) * position.position_size
        else:
            pnl = (position.entry_price - exit_price) * position.position_size
        
        # اعمال slippage
        if self.config.slippage > 0:
            if position.direction == "LONG":
                pnl -= self.config.slippage * position.notional
            else:
                pnl -= self.config.slippage * position.notional
        
        # اعمال commission
        if self.config.commission > 0:
            pnl -= self.config.commission * position.notional * 2  # entry + exit
        
        position.exit_price = exit_price
        position.exit_timestamp = exit_timestamp
        position.exit_reason = exit_reason
        position.realized_pnl = pnl
        position.is_open = False
        
        # R:R واقعی
        risk = abs(position.entry_price - position.stop_loss)
        reward = abs(exit_price - position.entry_price)
        rr_realized = reward / risk if risk > 0 else 0.0
        
        trade_record = TradeRecord(
            trade_id=f"TRD_{self._trade_counter}",
            signal_id=position.signal_id,
            symbol=position.symbol,
            direction=position.direction,
            entry_timestamp=position.entry_timestamp,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            position_size=position.position_size,
            risk_amount=position.risk_amount,
            exit_timestamp=exit_timestamp,
            exit_price=exit_price,
            exit_reason=exit_reason,
            realized_pnl=pnl,
            rr_realized=rr_realized
        )
        
        self._trades.append(trade_record)
        
        # به‌روزرسانی equity
        self._equity += pnl
        
        # به‌روزرسانی drawdown
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity
        
        drawdown = self._peak_equity - self._equity
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown
        
        self._open_position = None
    
    def _build_result(self) -> BacktestResult:
        """ساخت نتیجه نهایی"""
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.realized_pnl > 0)
        losing_trades = sum(1 for t in self._trades if t.realized_pnl <= 0)
        
        gross_profit = sum(t.realized_pnl for t in self._trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in self._trades if t.realized_pnl < 0))
        
        net_profit = self._equity - self.config.initial_equity
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
            float('inf') if gross_profit > 0 else 0.0
        )
        
        max_drawdown_pct = (
            self._max_drawdown / self._peak_equity if self._peak_equity > 0 else 0.0
        )
        
        average_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        average_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
        
        average_rr = sum(t.rr_realized for t in self._trades) / total_trades if total_trades > 0 else 0.0
        
        return BacktestResult(
            initial_equity=self.config.initial_equity,
            final_equity=self._equity,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            profit_factor=profit_factor if profit_factor != float('inf') else 0.0,
            max_drawdown=self._max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            average_win=average_win,
            average_loss=average_loss,
            average_rr=average_rr,
            trades=self._trades.copy()
        )
