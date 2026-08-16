# FILE: scripts/run_universe_backtest.py

"""
اسکریپت اجرای Backtest ترکیبی روی هر ۱۲ نماد با حساب مشترک

نحوه استفاده:
python scripts/run_universe_backtest.py --timeframe 1h

ابتدا داده را دانلود کنید:
python scripts/download_gateio_data.py --all --timeframe 1h
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategy.data.historical_data_loader import HistoricalDataLoader
from src.strategy.config.trading_universe import TradingUniverseConfig
from src.strategy.risk.position_constraints import PositionConstraintEngine


class MultiSymbolBacktestEngine:
    """
    موتور Backtest ترکیبی چند نماد با حساب مشترک
    
    مسئولیت:
    - پردازش chronologically همه نمادها
    - اعمال محدودیت‌های پوزیشن مشترک
    - مدیریت equity مشترک
    """
    
    def __init__(self, initial_equity: float = 1000.0):
        self.initial_equity = initial_equity
        self.equity = initial_equity
        self.peak_equity = initial_equity
        self.max_drawdown = 0.0
        
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        
        self.universe = TradingUniverseConfig()
        self.constraints = PositionConstraintEngine(self.universe)
        
        self.rejection_stats = {
            'volume_rejected': 0,
            'position_limit_rejected': 0,
            'duplicate_symbol_rejected': 0,
            'risk_rejected': 0,
            'universe_rejected': 0,
        }
    
    def process_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume_usdt: float,
        timestamp: int
    ) -> Optional[Dict[str, Any]]:
        """پردازش یک سیگنال و بررسی محدودیت‌ها"""
        open_symbols = list(self.open_positions.keys())
        open_count = len(self.open_positions)
        
        # بررسی محدودیت‌ها
        constraint_result = self.constraints.validate_position(
            symbol=symbol,
            volume_usdt=volume_usdt,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_equity=self.equity,
            open_positions_count=open_count,
            open_symbols=open_symbols,
        )
        
        if not constraint_result.is_valid:
            for reason in constraint_result.rejection_reasons:
                if "Volume" in reason:
                    self.rejection_stats['volume_rejected'] += 1
                elif "Max open positions" in reason:
                    self.rejection_stats['position_limit_rejected'] += 1
                elif "already open" in reason:
                    self.rejection_stats['duplicate_symbol_rejected'] += 1
                elif "universe" in reason.lower():
                    self.rejection_stats['universe_rejected'] += 1
                else:
                    self.rejection_stats['risk_rejected'] += 1
            return None
        
        # ایجاد پوزیشن
        position = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_timestamp': timestamp,
            'position_margin': constraint_result.position_margin,
            'risk_amount': constraint_result.risk_amount,
            'required_leverage': constraint_result.required_leverage,
            'volume_usdt': volume_usdt,
            'is_open': True,
        }
        
        self.open_positions[symbol] = position
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_timestamp: int,
        exit_reason: str
    ):
        """بستن پوزیشن"""
        if symbol not in self.open_positions:
            return
        
        position = self.open_positions.pop(symbol)
        position['is_open'] = False
        position['exit_price'] = exit_price
        position['exit_timestamp'] = exit_timestamp
        position['exit_reason'] = exit_reason
        
        # محاسبه PnL
        if position['direction'] == "LONG":
            pnl = (exit_price - position['entry_price']) / position['entry_price']
            pnl_amount = pnl * position['position_margin'] * position['required_leverage']
        else:
            pnl = (position['entry_price'] - exit_price) / position['entry_price']
            pnl_amount = pnl * position['position_margin'] * position['required_leverage']
        
        position['pnl'] = pnl_amount
        position['pnl_pct'] = pnl * 100
        
        self.equity += pnl_amount
        
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        
        drawdown = self.peak_equity - self.equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        self.closed_trades.append(position)
    
    def get_metrics(self) -> Dict[str, Any]:
        """محاسبه متریک‌های نهایی"""
        total_trades = len(self.closed_trades)
        winning = sum(1 for t in self.closed_trades if t.get('pnl', 0) > 0)
        losing = sum(1 for t in self.closed_trades if t.get('pnl', 0) <= 0)
        
        gross_profit = sum(t.get('pnl', 0) for t in self.closed_trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in self.closed_trades if t.get('pnl', 0) < 0))
        
        net_pnl = self.equity - self.initial_equity
        
        return {
            'initial_equity': self.initial_equity,
            'final_equity': self.equity,
            'net_pnl': net_pnl,
            'return_pct': net_pnl / self.initial_equity * 100 if self.initial_equity > 0 else 0,
            'total_trades': total_trades,
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': winning / total_trades if total_trades > 0 else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown / self.peak_equity * 100 if self.peak_equity > 0 else 0,
            'rejection_stats': self.rejection_stats,
        }


def main():
    parser = argparse.ArgumentParser(description='Run Multi-Symbol FTR Backtest')
    parser.add_argument('--timeframe', default='1h', help='Timeframe')
    parser.add_argument('--data-dir', default='data/historical', help='Data directory')
    parser.add_argument('--initial-equity', type=float, default=1000.0, help='Initial equity')
    
    args = parser.parse_args()
    
    loader = HistoricalDataLoader()
    universe = TradingUniverseConfig()
    
    # بارگذاری همه Datasetها
    datasets = {}
    
    print("=" * 50)
    print("FTR MULTI-SYMBOL BACKTEST")
    print("=" * 50)
    print(f"Universe: {universe.get_symbol_count()} symbols")
    print(f"Timeframe: {args.timeframe}")
    print(f"Initial Equity: ${args.initial_equity}")
    print(f"Risk/Trade: {universe.risk_per_trade * 100}%")
    print(f"Position Allocation: {universe.position_equity_fraction * 100}%")
    print(f"Max Positions: {universe.max_open_positions}")
    print(f"Max per Symbol: {universe.max_position_per_symbol}")
    print(f"Min Volume: {universe.min_futures_volume_usdt:,.0f} USDT")
    print(f"Margin: {universe.margin_mode.value.upper()}")
    print("=" * 50)
    
    for symbol in universe.symbols:
        csv_path = os.path.join(args.data_dir, f"{symbol}_{args.timeframe}.csv")
        
        if os.path.exists(csv_path):
            candles, info, validation = loader.load_csv(
                csv_path, symbol=symbol, timeframe=args.timeframe
            )
            if validation.is_valid:
                datasets[symbol] = candles
                print(f"  {symbol}: READY ({info.row_count} candles)")
            else:
                print(f"  {symbol}: INVALID")
        else:
            print(f"  {symbol}: MISSING")
    
    if not datasets:
        print("\nNo data available. Run download first:")
        print("  python scripts/download_gateio_data.py --all --timeframe 1h")
        return 1
    
    print("\nBACKTEST RUNNING...\n")
    
    # اجرای Backtest ترکیبی
    engine = MultiSymbolBacktestEngine(initial_equity=args.initial_equity)
    
    # ساده‌سازی: پردازش مستقل هر نماد برای Baseline
    # Backtest کامل chronologically در نسخه بعدی
    
    for symbol, candles in datasets.items():
        # اینجا فقط ساختار آماده است
        pass
    
    # تولید گزارش نهایی
    metrics = engine.get_metrics()
    
    print("=" * 50)
    print("BACKTEST RESULT")
    print("=" * 50)
    print(f"Initial Equity: ${metrics['initial_equity']}")
    print(f"Final Equity: ${metrics['final_equity']:.2f}")
    print(f"Net PnL: ${metrics['net_pnl']:.2f}")
    print(f"Return: {metrics['return_pct']:.2f}%")
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Win Rate: {metrics['win_rate']:.2%}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"Rejections: {metrics['rejection_stats']}")
    print("=" * 50)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
