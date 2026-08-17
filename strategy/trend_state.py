"""
استراتژی Multi-Timeframe Pullback Trading
4H روند اصلی + 1H تأیید + 5M ورود
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
import talib

class TrendStateStrategy:
    """
    استراتژی پولبک چند تایمفریمی
    """
    
    def __init__(self, config: Dict = None):
        self.config = {
            # EMA
            'ema_fast': 20,
            'ema_mid': 50,
            'ema_slow': 200,
            
            # ADX
            'adx_len': 14,
            'adx_trend_threshold': 20,
            'adx_strong_threshold': 30,
            
            # RSI
            'rsi_len': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'rsi_neutral_low': 40,
            'rsi_neutral_high': 60,
            
            # MACD
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            # حجم
            'volume_ma_len': 50,
            'volume_multiplier': 1.5,
            
            # Volatility
            'atr_len': 14,
            'atr_extreme_threshold': 3.0,  # ATR% بالای این = Extreme
            
            # مدیریت ریسک
            'atr_mult_sl': 2.0,
            'atr_mult_tp1': 3.0,
            'atr_mult_tp2': 5.0,
            'allow_short': True,
        }
        
        if config:
            self.config.update(config)
    
    def calculate_ema(self, series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()
    
    def calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """محاسبه MACD"""
        macd, signal, hist = talib.MACD(
            df['close'],
            fastperiod=self.config['macd_fast'],
            slowperiod=self.config['macd_slow'],
            signalperiod=self.config['macd_signal']
        )
        return macd, signal, hist
    
    def detect_trend_4h(self, df_4h: pd.DataFrame) -> str:
        """
        تشخیص روند در 4H
        Returns: 'bullish', 'bearish', 'sideways'
        """
        if df_4h is None or len(df_4h) < 200:
            return 'sideways'
        
        ema_20 = self.calculate_ema(df_4h['close'], 20)
        ema_50 = self.calculate_ema(df_4h['close'], 50)
        ema_200 = self.calculate_ema(df_4h['close'], 200)
        
        adx = talib.ADX(df_4h['high'], df_4h['low'], df_4h['close'], timeperiod=14)
        
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
        
        # روند صعودی قوی
        if ema_20.iloc[-1] > ema_50.iloc[-1] > ema_200.iloc[-1] and current_adx > self.config['adx_trend_threshold']:
            return 'bullish'
        
        # روند نزولی قوی
        if ema_20.iloc[-1] < ema_50.iloc[-1] < ema_200.iloc[-1] and current_adx > self.config['adx_trend_threshold']:
            return 'bearish'
        
        return 'sideways'
    
    def detect_trend_1h(self, df_1h: pd.DataFrame) -> str:
        """
        تشخیص روند در 1H
        """
        if df_1h is None or len(df_1h) < 100:
            return 'sideways'
        
        ema_20 = self.calculate_ema(df_1h['close'], 20)
        ema_50 = self.calculate_ema(df_1h['close'], 50)
        
        if ema_20.iloc[-1] > ema_50.iloc[-1]:
            return 'bullish'
        elif ema_20.iloc[-1] < ema_50.iloc[-1]:
            return 'bearish'
        return 'sideways'
    
    def find_swing_points(self, df: pd.DataFrame, lookback: int = 5) -> Tuple[pd.Series, pd.Series]:
        """
        پیدا کردن Swing High و Swing Low
        """
        swing_high = pd.Series(index=df.index, dtype=bool)
        swing_low = pd.Series(index=df.index, dtype=bool)
        
        for i in range(lookback, len(df) - lookback):
            # Swing High
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                swing_high.iloc[i] = True
            
            # Swing Low
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                swing_low.iloc[i] = True
        
        return swing_high, swing_low
    
    def detect_choch(self, df: pd.DataFrame, direction: str) -> pd.Series:
        """
        تشخیص CHOCH (Change of Character)
        """
        swing_high, swing_low = self.find_swing_points(df)
        
        choch = pd.Series(index=df.index, dtype=bool)
        
        if direction == 'bullish':
            # شکست آخرین Swing High
            for i in range(1, len(df)):
                if swing_low.iloc[i]:
                    recent_high = df['high'].iloc[max(0, i-20):i].max()
                    if df['close'].iloc[i] > recent_high:
                        choch.iloc[i] = True
        else:
            # شکست آخرین Swing Low
            for i in range(1, len(df)):
                if swing_high.iloc[i]:
                    recent_low = df['low'].iloc[max(0, i-20):i].min()
                    if df['close'].iloc[i] < recent_low:
                        choch.iloc[i] = True
        
        return choch
    
    def detect_bos(self, df: pd.DataFrame, direction: str) -> pd.Series:
        """
        تشخیص BOS (Break of Structure)
        """
        swing_high, swing_low = self.find_swing_points(df)
        
        bos = pd.Series(index=df.index, dtype=bool)
        
        if direction == 'bullish':
            for i in range(1, len(df)):
                if swing_low.iloc[i]:
                    prev_high = df['high'].iloc[max(0, i-30):i].max()
                    if df['high'].iloc[i] > prev_high:
                        bos.iloc[i] = True
        else:
            for i in range(1, len(df)):
                if swing_high.iloc[i]:
                    prev_low = df['low'].iloc[max(0, i-30):i].min()
                    if df['low'].iloc[i] < prev_low:
                        bos.iloc[i] = True
        
        return bos
    
    def calculate_signal_score(self, conditions: Dict) -> float:
        """
        محاسبه امتیاز سیگنال (0 تا 100)
        """
        weights = {
            'trend_alignment': 0.20,
            'momentum': 0.20,
            'structure': 0.20,
            'volume': 0.15,
            'volatility': 0.15,
            'pullback_quality': 0.10,
        }
        
        scores = {}
        
        # هم‌جهتی روند
        if conditions.get('trend_4h') == conditions.get('trend_1h'):
            scores['trend_alignment'] = 100
        else:
            scores['trend_alignment'] = 0
        
        # Momentum
        scores['momentum'] = conditions.get('momentum_score', 0)
        
        # Structure
        if conditions.get('choch') and conditions.get('bos'):
            scores['structure'] = 100
        elif conditions.get('choch') or conditions.get('bos'):
            scores['structure'] = 60
        else:
            scores['structure'] = 0
        
        # Volume
        scores['volume'] = 100 if conditions.get('volume_strong') else 40
        
        # Volatility
        scores['volatility'] = conditions.get('volatility_score', 50)
        
        # Pullback Quality
        scores['pullback_quality'] = conditions.get('pullback_score', 50)
        
        total = sum(scores[k] * weights[k] for k in weights)
        return total
    
    def generate_signals(self, df_5m: pd.DataFrame, df_1h: pd.DataFrame = None, df_4h: pd.DataFrame = None) -> pd.DataFrame:
        """
        تولید سیگنال‌ها
        """
        df = df_5m.copy()
        
        # ============ تشخیص روند ============
        trend_4h = self.detect_trend_4h(df_4h) if df_4h is not None else 'sideways'
        trend_1h = self.detect_trend_1h(df_1h) if df_1h is not None else 'sideways'
        
        # اگر 4H روند مشخصی نداشت
        if trend_4h == 'sideways':
            df['bull_signal'] = False
            df['bear_signal'] = False
            df['signal_score'] = 0
            return df
        
        # اگر 1H با 4H هم‌جهت نبود
        if trend_4h != trend_1h:
            df['bull_signal'] = False
            df['bear_signal'] = False
            df['signal_score'] = 0
            return df
        
        # ============ اندیکاتورها ============
        # RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config['rsi_len'])
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(df)
        
        # ATR
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.config['atr_len'])
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # حجم
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_len']).mean()
        df['volume_strong'] = df['volume'] > df['volume_ma'] * self.config['volume_multiplier']
        
        # ============ ساختار ============
        swing_high, swing_low = self.find_swing_points(df)
        
        choch_bull = self.detect_choch(df, 'bullish')
        choch_bear = self.detect_choch(df, 'bearish')
        bos_bull = self.detect_bos(df, 'bullish')
        bos_bear = self.detect_bos(df, 'bearish')
        
        # ============ تولید سیگنال ============
        df['signal_score'] = 0.0
        df['bull_signal'] = False
        df['bear_signal'] = False
        
        for i in range(50, len(df)):
            # شرایط LONG
            if trend_4h == 'bullish' and trend_1h == 'bullish':
                # Pullback: قیمت پایین‌تر از EMA20
                pullback = df['low'].iloc[i] < df['close'].ewm(span=20).mean().iloc[i]
                
                # Momentum Recovery
                rsi_recovering = df['rsi'].iloc[i] > df['rsi'].iloc[i-1] and df['rsi'].iloc[i] > 30
                macd_turning = df['macd_hist'].iloc[i] > df['macd_hist'].iloc[i-1]
                
                # Structure
                structure_ok = choch_bull.iloc[i] or bos_bull.iloc[i]
                
                # Volume
                volume_ok = df['volume_strong'].iloc[i]
                
                # Volatility
                vol_ok = df['atr_pct'].iloc[i] < self.config['atr_extreme_threshold']
                
                if pullback and rsi_recovering and structure_ok and volume_ok and vol_ok:
                    conditions = {
                        'trend_4h': 'bullish',
                        'trend_1h': 'bullish',
                        'momentum_score': min(100, df['rsi'].iloc[i]),
                        'choch': choch_bull.iloc[i],
                        'bos': bos_bull.iloc[i],
                        'volume_strong': volume_ok,
                        'volatility_score': 100 - df['atr_pct'].iloc[i] * 30,
                        'pullback_score': 70 if pullback else 0,
                    }
                    score = self.calculate_signal_score(conditions)
                    df.loc[df.index[i], 'signal_score'] = score
                    df.loc[df.index[i], 'bull_signal'] = score >= 70
            
            # شرایط SHORT
            if trend_4h == 'bearish' and trend_1h == 'bearish':
                # Pullback: قیمت بالاتر از EMA20
                pullback = df['high'].iloc[i] > df['close'].ewm(span=20).mean().iloc[i]
                
                # Momentum Recovery
                rsi_recovering = df['rsi'].iloc[i] < df['rsi'].iloc[i-1] and df['rsi'].iloc[i] < 70
                macd_turning = df['macd_hist'].iloc[i] < df['macd_hist'].iloc[i-1]
                
                # Structure
                structure_ok = choch_bear.iloc[i] or bos_bear.iloc[i]
                
                # Volume
                volume_ok = df['volume_strong'].iloc[i]
                
                # Volatility
                vol_ok = df['atr_pct'].iloc[i] < self.config['atr_extreme_threshold']
                
                if pullback and rsi_recovering and structure_ok and volume_ok and vol_ok:
                    conditions = {
                        'trend_4h': 'bearish',
                        'trend_1h': 'bearish',
                        'momentum_score': min(100, 100 - df['rsi'].iloc[i]),
                        'choch': choch_bear.iloc[i],
                        'bos': bos_bear.iloc[i],
                        'volume_strong': volume_ok,
                        'volatility_score': 100 - df['atr_pct'].iloc[i] * 30,
                        'pullback_score': 70 if pullback else 0,
                    }
                    score = self.calculate_signal_score(conditions)
                    df.loc[df.index[i], 'signal_score'] = score
                    df.loc[df.index[i], 'bear_signal'] = score >= 70
        
        # ============ حد ضرر و سود ============
        df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
        df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp1']
        df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp1']
        df['rr_ratio'] = self.config['atr_mult_tp1'] / self.config['atr_mult_sl']
        
        return df
