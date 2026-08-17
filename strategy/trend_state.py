"""
استراتژی Trend State - نسخه Python
تبدیل دقیق از Pine Script v6 به Python
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import talib

class TrendStateStrategy:
    """
    استراتژی Trend State با فیلترهای بهبود یافته
    """
    
    def __init__(self, config: Dict = None):
        """
        مقداردهی اولیه استراتژی
        
        Parameters:
        -----------
        config : Dict
            تنظیمات استراتژی
        """
        # تنظیمات پیش‌فرض
        self.config = {
            # هسته فیلتر
            'length': 14,
            'multiplier': 2.5,
            'offset': 0.5,
            'sigma': 1.0,
            'source_type': 'custom',
            
            # فیلتر روند
            'use_trend_filter': True,
            'trend_ma_len': 200,
            
            # فیلتر ADX (سختگیرانه‌تر)
            'use_adx_filter': True,
            'adx_len': 14,
            'adx_threshold': 30,    # از 20 به 30
            
            # فیلتر نوسان
            'use_vol_filter': True,
            'vol_len': 50,
            'vol_ratio_min': 0.8,
            'vol_ratio_max': 1.5,
            
            # فیلتر Bollinger Squeeze
            'use_bb_filter': True,
            'bb_len': 20,
            'bb_mult': 2.0,
            'bb_squeeze_threshold': 0.8,
            
            # مدیریت ریسک (حد ضرر دورتر)
            'use_atr_stop': True,
            'atr_len': 14,
            'atr_mult_sl': 3.5,     # از 2.5 به 3.5
            'use_atr_tp': True,
            'atr_mult_tp': 4.0,
            'allow_short': True,
        }
        
        # به‌روزرسانی با تنظیمات کاربر
        if config:
            self.config.update(config)
        
        # متغیرهای حالت
        self.filter_line = None
        self.trend = None
        
    def calculate_source(self, df: pd.DataFrame) -> pd.Series:
        """
        محاسبه منبع قیمت بر اساس نوع انتخاب شده
        """
        source_type = self.config['source_type']
        
        if source_type == 'close':
            return df['close']
        elif source_type == 'hl2':
            return (df['high'] + df['low']) / 2
        elif source_type == 'hlc3':
            return (df['high'] + df['low'] + df['close']) / 3
        elif source_type == 'ohlc4':
            return (df['open'] + df['high'] + df['low'] + df['close']) / 4
        elif source_type == 'hlcc4':
            return (df['high'] + df['low'] + 2 * df['close']) / 4
        elif source_type == 'occ3':
            return (df['open'] + 2 * df['close']) / 3
        else:  # custom
            return (df['open'] + 2 * df['high'] + 2 * df['low'] + 2 * df['close']) / 7
    
    def alma(self, series: pd.Series, length: int, offset: float, sigma: float) -> pd.Series:
        """
        محاسبه ALMA (Arnaud Legoux Moving Average)
        """
        m = offset * (length - 1)
        s = length / sigma
        
        weights = np.zeros(length)
        for i in range(length):
            weights[i] = np.exp(-0.5 * ((i - m) / s) ** 2)
        
        weights = weights / weights.sum()
        
        alma_values = series.rolling(window=length).apply(
            lambda x: np.sum(x * weights), raw=True
        )
        
        return alma_values
    
    def calculate_trend_state(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        محاسبه هسته فیلتر Trend State
        """
        src = self.calculate_source(df)
        
        movement = src.diff().abs()
        
        smooth_move = self.alma(
            movement, 
            self.config['length'], 
            self.config['offset'], 
            self.config['sigma']
        )
        
        adaptive_range = smooth_move * self.config['multiplier']
        
        filter_line = pd.Series(index=df.index, dtype=float)
        
        filter_line.iloc[0] = src.iloc[0] if not pd.isna(src.iloc[0]) else 0
        
        for i in range(1, len(df)):
            prev_filter = filter_line.iloc[i-1]
            
            if pd.isna(prev_filter) or pd.isna(adaptive_range.iloc[i]):
                filter_line.iloc[i] = src.iloc[i]
                continue
            
            upper = prev_filter + adaptive_range.iloc[i]
            lower = prev_filter - adaptive_range.iloc[i]
            
            if src.iloc[i] > upper:
                filter_line.iloc[i] = src.iloc[i] - adaptive_range.iloc[i]
            elif src.iloc[i] < lower:
                filter_line.iloc[i] = src.iloc[i] + adaptive_range.iloc[i]
            else:
                filter_line.iloc[i] = prev_filter
        
        trend = pd.Series(index=df.index, dtype=int)
        trend.iloc[0] = 0
        
        for i in range(1, len(df)):
            if filter_line.iloc[i] > filter_line.iloc[i-1]:
                trend.iloc[i] = 1
            elif filter_line.iloc[i] < filter_line.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1] if not pd.isna(trend.iloc[i-1]) else 0
        
        df['filter_line'] = filter_line
        df['trend'] = trend
        df['adaptive_range'] = adaptive_range
        df['smooth_move'] = smooth_move
        
        return df
    
    def calculate_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        محاسبه تمام فیلترهای کیفیت سیگنال
        """
        # 1. EMA 200
        if self.config['use_trend_filter']:
            df['trend_ma'] = talib.EMA(df['close'], timeperiod=self.config['trend_ma_len'])
            df['trend_ok_long'] = df['close'] > df['trend_ma']
            df['trend_ok_short'] = df['close'] < df['trend_ma']
        else:
            df['trend_ok_long'] = True
            df['trend_ok_short'] = True
        
        # 2. ADX + DI
        if self.config['use_adx_filter']:
            df['adx'] = talib.ADX(
                df['high'], 
                df['low'], 
                df['close'], 
                timeperiod=self.config['adx_len']
            )
            df['di_plus'] = talib.PLUS_DI(
                df['high'], 
                df['low'], 
                df['close'], 
                timeperiod=self.config['adx_len']
            )
            df['di_minus'] = talib.MINUS_DI(
                df['high'], 
                df['low'], 
                df['close'], 
                timeperiod=self.config['adx_len']
            )
            
            df['adx_ok'] = df['adx'] > self.config['adx_threshold']
            df['adx_trend_ok_long'] = df['adx_ok'] & (df['di_plus'] > df['di_minus'])
            df['adx_trend_ok_short'] = df['adx_ok'] & (df['di_minus'] > df['di_plus'])
        else:
            df['adx_trend_ok_long'] = True
            df['adx_trend_ok_short'] = True
        
        # 3. Volatility Filter
        if self.config['use_vol_filter']:
            df['avg_range'] = df['adaptive_range'].rolling(
                window=self.config['vol_len']
            ).mean()
            
            df['vol_ratio'] = df['adaptive_range'] / df['avg_range']
            
            df['vol_ok'] = (
                (df['vol_ratio'] >= self.config['vol_ratio_min']) & 
                (df['vol_ratio'] <= self.config['vol_ratio_max'])
            )
        else:
            df['vol_ok'] = True
        
        # 4. Bollinger Squeeze
        if self.config['use_bb_filter']:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'],
                timeperiod=self.config['bb_len'],
                nbdevup=self.config['bb_mult'],
                nbdevdn=self.config['bb_mult'],
                matype=0
            )
            
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_width_avg'] = df['bb_width'].rolling(window=self.config['bb_len']).mean()
            
            df['bb_squeeze'] = df['bb_width'] < df['bb_width_avg'] * self.config['bb_squeeze_threshold']
            df['bb_ok'] = ~df['bb_squeeze']
        else:
            df['bb_ok'] = True
        
        # 5. ATR برای مدیریت ریسک
        if self.config['use_atr_stop'] or self.config['use_atr_tp']:
            df['atr'] = talib.ATR(
                df['high'], 
                df['low'], 
                df['close'], 
                timeperiod=self.config['atr_len']
            )
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        تولید سیگنال‌های معاملاتی با تمام فیلترها
        """
        # محاسبه هسته فیلتر
        df = self.calculate_trend_state(df)
        
        # محاسبه فیلترها
        df = self.calculate_filters(df)
        
        # تشخیص تغییر روند
        df['trend_change'] = df['trend'].diff()
        
        # سیگنال‌های خام
        df['raw_bull'] = (df['trend_change'] > 0) & (df['trend'] == 1)
        df['raw_bear'] = (df['trend_change'] < 0) & (df['trend'] == -1)
        
        # اعمال فیلترها
        df['bull_signal'] = (
            df['raw_bull'] & 
            df['trend_ok_long'] & 
            df['adx_trend_ok_long'] & 
            df['vol_ok'] & 
            df['bb_ok']
        )
        
        df['bear_signal'] = (
            df['raw_bear'] & 
            df['trend_ok_short'] & 
            df['adx_trend_ok_short'] & 
            df['vol_ok'] & 
            df['bb_ok']
        )
        
        # محاسبه حد ضرر و سود
        if self.config['use_atr_stop']:
            df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
            df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        
        if self.config['use_atr_tp']:
            df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp']
            df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp']
        
        # محاسبه نسبت ریسک به ریوارد
        if self.config['use_atr_stop'] and self.config['use_atr_tp']:
            df['rr_ratio'] = self.config['atr_mult_tp'] / self.config['atr_mult_sl']
        
        return df
    
    def get_signal_info(self, df: pd.DataFrame, index: int) -> Dict:
        """
        دریافت اطلاعات کامل سیگنال در یک نقطه خاص
        """
        if index < 0 or index >= len(df):
            return None
        
        row = df.iloc[index]
        
        signal_info = {
            'timestamp': df.index[index],
            'close': row['close'],
            'trend': row['trend'],
            'filter_line': row['filter_line'],
            'adaptive_range': row['adaptive_range'],
            'bull_signal': row['bull_signal'],
            'bear_signal': row['bear_signal'],
        }
        
        if 'trend_ma' in df.columns:
            signal_info['trend_ma'] = row['trend_ma']
        if 'adx' in df.columns:
            signal_info['adx'] = row['adx']
            signal_info['di_plus'] = row['di_plus']
            signal_info['di_minus'] = row['di_minus']
        if 'vol_ratio' in df.columns:
            signal_info['vol_ratio'] = row['vol_ratio']
        if 'bb_width' in df.columns:
            signal_info['bb_width'] = row['bb_width']
            signal_info['bb_squeeze'] = row['bb_squeeze']
        
        if 'long_stop' in df.columns:
            signal_info['long_stop'] = row['long_stop']
            signal_info['long_tp'] = row['long_tp']
        if 'short_stop' in df.columns:
            signal_info['short_stop'] = row['short_stop']
            signal_info['short_tp'] = row['short_tp']
        
        return signal_info
