"""
استراتژی EMA + RSI Multi-Timeframe
سیگنال خرید: EMA20 > EMA200 در ۱h + RSI از زیر ۳۰ به بالا در ۵m + حجم بالا
سیگنال فروش: EMA20 < EMA200 در ۱h + RSI از بالای ۷۰ به پایین در ۵m + حجم بالا
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import talib

class TrendStateStrategy:
    """
    استراتژی ترکیبی EMA و RSI با تایید حجم
    """
    
    def __init__(self, config: Dict = None):
        """
        مقداردهی اولیه استراتژی
        """
        self.config = {
            # EMA
            'ema_fast': 20,
            'ema_slow': 200,
            
            # RSI
            'rsi_len': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            
            # حجم
            'volume_ma_len': 50,
            'volume_multiplier': 1.5,  # حجم باید ۱.۵ برابر میانگین باشد
            
            # مدیریت ریسک
            'use_atr_stop': True,
            'atr_len': 14,
            'atr_mult_sl': 3.5,
            'use_atr_tp': True,
            'atr_mult_tp': 4.0,
            'allow_short': True,
        }
        
        if config:
            self.config.update(config)
    
    def calculate_ema(self, series: pd.Series, length: int) -> pd.Series:
        """محاسبه EMA"""
        return series.ewm(span=length, adjust=False).mean()
    
    def generate_signals(self, df: pd.DataFrame, df_1h: pd.DataFrame = None) -> pd.DataFrame:
        """
        تولید سیگنالهای معاملاتی
        
        Parameters:
        -----------
        df : pd.DataFrame
            دادههای تایمفریم ۵ دقیقه
        df_1h : pd.DataFrame
            دادههای تایمفریم ۱ ساعته (برای فیلتر روند)
            
        Returns:
        --------
        pd.DataFrame
            دیتافریم با سیگنالها
        """
        # ============ فیلتر روند ۱ ساعته ============
        if df_1h is not None and len(df_1h) > 0:
            # محاسبه EMA روی ۱ ساعته
            ema_fast_1h = self.calculate_ema(df_1h['close'], self.config['ema_fast'])
            ema_slow_1h = self.calculate_ema(df_1h['close'], self.config['ema_slow'])
            
            # وضعیت روند ۱ ساعته
            hourly_bullish = ema_fast_1h.iloc[-1] > ema_slow_1h.iloc[-1]
            hourly_bearish = ema_fast_1h.iloc[-1] < ema_slow_1h.iloc[-1]
        else:
            # اگر داده ۱ ساعته نبود، فقط ۵ دقیقه
            hourly_bullish = True
            hourly_bearish = True
        
        # ============ محاسبه RSI روی ۵ دقیقه ============
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config['rsi_len'])
        
        # ============ محاسبه حجم ============
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_len']).mean()
        df['volume_high'] = df['volume'] > df['volume_ma'] * self.config['volume_multiplier']
        
        # ============ سیگنال خرید ============
        # RSI از زیر ۳۰ به بالا حرکت کرده
        rsi_cross_up = (df['rsi'] > self.config['rsi_oversold']) & (df['rsi'].shift(1) <= self.config['rsi_oversold'])
        
        # سیگنال خرید کامل
        df['bull_signal'] = (
            hourly_bullish &          # روند ۱h صعودی
            rsi_cross_up &            # RSI از زیر ۳۰ عبور کرده
            df['volume_high']         # حجم بالا
        )
        
        # ============ سیگنال فروش ============
        # RSI از بالای ۷۰ به پایین حرکت کرده
        rsi_cross_down = (df['rsi'] < self.config['rsi_overbought']) & (df['rsi'].shift(1) >= self.config['rsi_overbought'])
        
        # سیگنال فروش کامل
        df['bear_signal'] = (
            hourly_bearish &          # روند ۱h نزولی
            rsi_cross_down &          # RSI از بالای ۷۰ عبور کرده
            df['volume_high']         # حجم بالا
        )
        
        # ============ مدیریت ریسک با ATR ============
        if self.config['use_atr_stop'] or self.config['use_atr_tp']:
            df['atr'] = talib.ATR(
                df['high'], 
                df['low'], 
                df['close'], 
                timeperiod=self.config['atr_len']
            )
        
        if self.config['use_atr_stop']:
            df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
            df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        
        if self.config['use_atr_tp']:
            df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp']
            df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp']
        
        # نسبت ریسک به ریوارد
        if self.config['use_atr_stop'] and self.config['use_atr_tp']:
            df['rr_ratio'] = self.config['atr_mult_tp'] / self.config['atr_mult_sl']
        
        return df
