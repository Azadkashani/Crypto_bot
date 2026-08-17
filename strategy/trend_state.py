"""
استراتژی Supertrend + RSI + Volume Multi-Timeframe
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import talib

class TrendStateStrategy:
    """
    استراتژی Supertrend با تایید RSI و حجم
    """
    
    def __init__(self, config: Dict = None):
        self.config = {
            # Supertrend
            'st_period': 10,
            'st_multiplier': 3.0,
            
            # RSI
            'rsi_len': 14,
            'rsi_bull_threshold': 50,
            'rsi_bear_threshold': 50,
            
            # حجم
            'volume_ma_len': 50,
            'volume_multiplier': 1.5,
            
            # ADX
            'use_adx_filter': True,
            'adx_len': 14,
            'adx_threshold': 20,
            
            # مدیریت ریسک
            'use_atr_stop': True,
            'atr_len': 14,
            'atr_mult_sl': 2.0,
            'use_atr_tp': True,
            'atr_mult_tp': 4.0,
            'allow_short': True,
        }
        
        if config:
            self.config.update(config)
    
    def calculate_supertrend(self, df: pd.DataFrame, period: int, multiplier: float) -> pd.Series:
        """محاسبه Supertrend"""
        atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        
        hl2 = (df['high'] + df['low']) / 2
        
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            if pd.isna(atr.iloc[i]):
                continue
            
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1  # صعودی
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1  # نزولی
            else:
                direction.iloc[i] = direction.iloc[i-1] if i > 0 else 1
            
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
        
        return supertrend, direction
    
    def generate_signals(self, df: pd.DataFrame, df_1h: pd.DataFrame = None) -> pd.DataFrame:
        """تولید سیگنالها"""
        
        # ============ Supertrend ۱ ساعته ============
        if df_1h is not None and len(df_1h) > 0:
            st_1h, dir_1h = self.calculate_supertrend(
                df_1h, 
                self.config['st_period'], 
                self.config['st_multiplier']
            )
            hourly_bullish = dir_1h.iloc[-1] == 1
            hourly_bearish = dir_1h.iloc[-1] == -1
        else:
            hourly_bullish = True
            hourly_bearish = True
        
        # ============ Supertrend ۵ دقیقه ============
        st_5m, dir_5m = self.calculate_supertrend(
            df, 
            self.config['st_period'], 
            self.config['st_multiplier']
        )
        
        # تغییر جهت Supertrend
        st_cross_up = (dir_5m == 1) & (dir_5m.shift(1) == -1)
        st_cross_down = (dir_5m == -1) & (dir_5m.shift(1) == 1)
        
        # ============ RSI ============
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config['rsi_len'])
        rsi_bull = df['rsi'] > self.config['rsi_bull_threshold']
        rsi_bear = df['rsi'] < self.config['rsi_bear_threshold']
        
        # ============ حجم ============
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_len']).mean()
        df['volume_high'] = df['volume'] > df['volume_ma'] * self.config['volume_multiplier']
        
        # ============ ADX ============
        if self.config['use_adx_filter']:
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.config['adx_len'])
            df['adx_ok'] = df['adx'] > self.config['adx_threshold']
        else:
            df['adx_ok'] = True
        
        # ============ سیگنالها ============
        df['bull_signal'] = (
            hourly_bullish &
            st_cross_up &
            rsi_bull &
            df['volume_high'] &
            df['adx_ok']
        )
        
        df['bear_signal'] = (
            hourly_bearish &
            st_cross_down &
            rsi_bear &
            df['volume_high'] &
            df['adx_ok']
        )
        
        # ============ ATR ============
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.config['atr_len'])
        
        df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
        df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp']
        df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp']
        df['rr_ratio'] = self.config['atr_mult_tp'] / self.config['atr_mult_sl']
        
        return df
