"""
استراتژی EMA + RSI بهینه شده
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import talib

class TrendStateStrategy:
    """
    استراتژی ترکیبی EMA و RSI با فیلترهای بهبود یافته
    """
    
    def __init__(self, config: Dict = None):
        self.config = {
            # EMA
            'ema_fast': 20,
            'ema_slow': 200,
            
            # RSI (سختگیرانهتر)
            'rsi_len': 14,
            'rsi_oversold': 25,      # از 30 به 25
            'rsi_overbought': 75,    # از 70 به 75
            
            # حجم (قویتر)
            'volume_ma_len': 50,
            'volume_multiplier': 2.0,  # از 1.5 به 2.0
            
            # فیلتر ADX
            'use_adx_filter': True,
            'adx_len': 14,
            'adx_threshold': 20,
            
            # مدیریت ریسک
            'use_atr_stop': True,
            'atr_len': 14,
            'atr_mult_sl': 2.5,
            'use_atr_tp': True,
            'atr_mult_tp': 5.0,
            'allow_short': True,
        }
        
        if config:
            self.config.update(config)
    
    def calculate_ema(self, series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()
    
    def generate_signals(self, df: pd.DataFrame, df_1h: pd.DataFrame = None) -> pd.DataFrame:
        # فیلتر روند ۱ ساعته
        if df_1h is not None and len(df_1h) > 0:
            ema_fast_1h = self.calculate_ema(df_1h['close'], self.config['ema_fast'])
            ema_slow_1h = self.calculate_ema(df_1h['close'], self.config['ema_slow'])
            hourly_bullish = ema_fast_1h.iloc[-1] > ema_slow_1h.iloc[-1]
            hourly_bearish = ema_fast_1h.iloc[-1] < ema_slow_1h.iloc[-1]
        else:
            hourly_bullish = True
            hourly_bearish = True
        
        # RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config['rsi_len'])
        
        # حجم
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_len']).mean()
        df['volume_high'] = df['volume'] > df['volume_ma'] * self.config['volume_multiplier']
        
        # ADX
        if self.config['use_adx_filter']:
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.config['adx_len'])
            df['adx_ok'] = df['adx'] > self.config['adx_threshold']
        else:
            df['adx_ok'] = True
        
        # سیگنال خرید
        rsi_cross_up = (df['rsi'] > self.config['rsi_oversold']) & (df['rsi'].shift(1) <= self.config['rsi_oversold'])
        
        # تأیید کندل - کندل بعدی باید صعودی باشد
        candle_confirms_bull = df['close'] > df['open']
        
        df['bull_signal'] = (
            hourly_bullish &
            rsi_cross_up &
            df['volume_high'] &
            df['adx_ok'] &
            candle_confirms_bull
        )
        
        # سیگنال فروش
        rsi_cross_down = (df['rsi'] < self.config['rsi_overbought']) & (df['rsi'].shift(1) >= self.config['rsi_overbought'])
        
        # تأیید کندل - کندل بعدی باید نزولی باشد
        candle_confirms_bear = df['close'] < df['open']
        
        df['bear_signal'] = (
            hourly_bearish &
            rsi_cross_down &
            df['volume_high'] &
            df['adx_ok'] &
            candle_confirms_bear
        )
        
        # ATR
        if self.config['use_atr_stop'] or self.config['use_atr_tp']:
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.config['atr_len'])
        
        if self.config['use_atr_stop']:
            df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
            df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        
        if self.config['use_atr_tp']:
            df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp']
            df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp']
        
        if self.config['use_atr_stop'] and self.config['use_atr_tp']:
            df['rr_ratio'] = self.config['atr_mult_tp'] / self.config['atr_mult_sl']
        
        return df
