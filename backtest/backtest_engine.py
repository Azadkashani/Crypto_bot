"""
موتور بکتست برای استراتژی Trend State
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    موتور بکتست ساده برای تست استراتژی
    """
    
    def __init__(self, initial_capital: float = 1000, commission_rate: float = 0.0005, slippage: float = 0.0002):
        """
        مقداردهی اولیه
        
        Parameters:
        -----------
        initial_capital : float
            سرمایه اولیه
        commission_rate : float
            نرخ کارمزد (۰.۰۵٪ = 0.0005)
        slippage : float
            اسلیپیج (۰.۰۲٪ = 0.0002)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        
        # متغیرهای حالت
        self.capital = initial_capital
        self.position = None
        self.trades = []
        
    def calculate_commission(self, trade_value: float) -> float:
        """محاسبه کارمزد"""
        return trade_value * self.commission_rate
    
    def calculate_slippage(self, price: float) -> float:
        """محاسبه اسلیپیج"""
        return price * self.slippage
    
    def open_position(self, timestamp, symbol, side, price, quantity, stop_loss=None, take_profit=None):
        """باز کردن پوزیشن"""
        # اعمال اسلیپیج
        if side == 'long':
            entry_price = price + self.calculate_slippage(price)
        else:
            entry_price = price - self.calculate_slippage(price)
        
        # محاسبه کارمزد
        trade_value = entry_price * quantity
        commission = self.calculate_commission(trade_value)
        
        # ثبت پوزیشن
        self.position = {
            'timestamp': timestamp,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'commission': commission,
            'entry_value': trade_value,
        }
        
        # کم کردن کارمزد از سرمایه
        self.capital -= commission
        
        logger.info(f"🔵 باز کردن {side} روی {symbol} @ {entry_price:.2f} - Qty: {quantity}")
    
    def close_position(self, timestamp, price, reason='signal'):
        """بستن پوزیشن"""
        if not self.position:
            return None
        
        # اعمال اسلیپیج
        if self.position['side'] == 'long':
            exit_price = price - self.calculate_slippage(price)
        else:
            exit_price = price + self.calculate_slippage(price)
        
        # محاسبه سود/ضرر
        if self.position['side'] == 'long':
            pnl = (exit_price - self.position['entry_price']) * self.position['quantity']
        else:
            pnl = (self.position['entry_price'] - exit_price) * self.position['quantity']
        
        # محاسبه کارمزد
        exit_value = exit_price * self.position['quantity']
        commission = self.calculate_commission(exit_value)
        
        # سود/ضرر خالص
        net_pnl = pnl - commission - self.position['commission']
        
        # بهروزرسانی سرمایه
        self.capital += net_pnl
        
        # ثبت معامله
        trade = {
            'timestamp': timestamp,
            'symbol': self.position['symbol'],
            'side': self.position['side'],
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'quantity': self.position['quantity'],
            'pnl': pnl,
            'commission_total': commission + self.position['commission'],
            'net_pnl': net_pnl,
            'reason': reason,
            'duration': timestamp - self.position['timestamp'],
        }
        
        self.trades.append(trade)
        
        logger.info(f"🔴 بستن {self.position['side']} @ {exit_price:.2f} - PnL: {net_pnl:.2f} USDT")
        
        # پاک کردن پوزیشن
        self.position = None
        
        return trade
    
    def check_stop_loss_take_profit(self, timestamp, high, low):
        """بررسی حد ضرر و سود"""
        if not self.position:
            return False
        
        # بررسی حد ضرر
        if self.position['stop_loss']:
            if self.position['side'] == 'long' and low <= self.position['stop_loss']:
                self.close_position(timestamp, self.position['stop_loss'], 'stop_loss')
                return True
            elif self.position['side'] == 'short' and high >= self.position['stop_loss']:
                self.close_position(timestamp, self.position['stop_loss'], 'stop_loss')
                return True
        
        # بررسی حد سود
        if self.position['take_profit']:
            if self.position['side'] == 'long' and high >= self.position['take_profit']:
                self.close_position(timestamp, self.position['take_profit'], 'take_profit')
                return True
            elif self.position['side'] == 'short' and low <= self.position['take_profit']:
                self.close_position(timestamp, self.position['take_profit'], 'take_profit')
                return True
        
        return False
    
    def run_backtest(self, df: pd.DataFrame, signals: pd.DataFrame, quantity_percent: float = 25) -> Dict:
        """
        اجرای بکتست
        
        Parameters:
        -----------
        df : pd.DataFrame
            دادههای قیمتی
        signals : pd.DataFrame
            سیگنالهای معاملاتی
        quantity_percent : float
            درصد سرمایه برای هر معامله
            
        Returns:
        --------
        Dict
            نتایج بکتست
        """
        # ترکیب دادهها و سیگنالها
        data = df.copy()
        data['bull_signal'] = signals['bull_signal']
        data['bear_signal'] = signals['bear_signal']
        
        if 'long_stop' in signals.columns:
            data['long_stop'] = signals['long_stop']
        if 'long_tp' in signals.columns:
            data['long_tp'] = signals['long_tp']
        if 'short_stop' in signals.columns:
            data['short_stop'] = signals['short_stop']
        if 'short_tp' in signals.columns:
            data['short_tp'] = signals['short_tp']
        
        # حذف ردیفهای NaN
        data = data.dropna()
        
        # شبیهسازی معاملات
        for i in range(1, len(data)):
            timestamp = data.index[i]
            row = data.iloc[i]
            prev_row = data.iloc[i-1]
            
            # بررسی حد ضرر و سود
            if self.position:
                if self.check_stop_loss_take_profit(timestamp, row['high'], row['low']):
                    continue
            
            # بررسی سیگنالها
            if row['bull_signal'] and not self.position:
                quantity = (self.capital * quantity_percent / 100) / row['close']
                self.open_position(
                    timestamp=timestamp,
                    symbol='TEST',
                    side='long',
                    price=row['close'],
                    quantity=quantity,
                    stop_loss=row.get('long_stop'),
                    take_profit=row.get('long_tp'),
                )
            
            elif row['bear_signal'] and not self.position:
                quantity = (self.capital * quantity_percent / 100) / row['close']
                self.open_position(
                    timestamp=timestamp,
                    symbol='TEST',
                    side='short',
                    price=row['close'],
                    quantity=quantity,
                    stop_loss=row.get('short_stop'),
                    take_profit=row.get('short_tp'),
                )
            
            # بستن پوزیشن در سیگنال مخالف
            elif row['bull_signal'] and self.position and self.position['side'] == 'short':
                self.close_position(timestamp, row['close'], 'signal_reverse')
            elif row['bear_signal'] and self.position and self.position['side'] == 'long':
                self.close_position(timestamp, row['close'], 'signal_reverse')
        
        # بستن پوزیشن باز در پایان
        if self.position:
            self.close_position(data.index[-1], data.iloc[-1]['close'], 'end_of_backtest')
        
        # محاسبه نتایج
        results = self.calculate_results()
        
        return results
    
    def calculate_results(self) -> Dict:
        """محاسبه نتایج بکتست"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'final_capital': self.capital,
                'return_pct': 0,
            }
        
        winning_trades = [t for t in self.trades if t['net_pnl'] > 0]
        losing_trades = [t for t in self.trades if t['net_pnl'] <= 0]
        
        total_pnl = sum(t['net_pnl'] for t in self.trades)
        avg_win = np.mean([t['net_pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['net_pnl'] for t in losing_trades]) if losing_trades else 0
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.trades) * 100 if self.trades else 0,
            'total_pnl': total_pnl,
            'final_capital': self.capital,
            'return_pct': (self.capital / self.initial_capital - 1) * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss else 0,
        }
