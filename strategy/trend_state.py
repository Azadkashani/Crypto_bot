"""
استراتژی Head and Shoulders Pattern
تشخیص الگوی سر و شانه با تأیید حجم و تایمفریم بالاتر
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
import talib

class TrendStateStrategy:
    """
    استراتژی الگوی سر و شانه
    """
    
    def __init__(self, config: Dict = None):
        self.config = {
            # Swing Detection
            'swing_lookback': 10,       # تعداد کندل برای تشخیص Swing
            
            # الگو
            'min_shoulder_distance': 10,  # حداقل فاصله بین شانهها
            'shoulder_height_tolerance': 0.10,  # تلورانس ۱۰٪
            
            # حجم
            'volume_ma_len': 50,
            'volume_breakout_multiplier': 1.5,  # حجم شکست
            
            # امتیاز
            'min_score': 70,  # حداقل امتیاز ۷۰٪
            
            # مدیریت ریسک
            'atr_len': 14,
            'atr_mult_sl': 2.0,
            'atr_mult_tp': 4.0,
            'allow_short': True,
        }
        
        if config:
            self.config.update(config)
    
    def find_swing_points(self, df: pd.DataFrame, lookback: int = 10) -> Tuple[pd.Series, pd.Series]:
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
    
    def find_head_shoulders_bearish(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        تشخیص الگوی سر و شانه سقف (Bearish)
        
        Returns:
        --------
        Dict or None
            اطلاعات الگو شامل:
            - left_shoulder_idx
            - head_idx
            - right_shoulder_idx
            - neckline_level
            - neckline_slope
            - score
        """
        swing_high, swing_low = self.find_swing_points(df, self.config['swing_lookback'])
        
        # استخراج Swing High ها
        swing_high_indices = df.index[swing_high].tolist()
        
        if len(swing_high_indices) < 3:
            return None
        
        # بررسی ترکیبهای سهگانه
        for i in range(len(swing_high_indices) - 2):
            left_idx = swing_high_indices[i]
            head_idx = swing_high_indices[i+1]
            right_idx = swing_high_indices[i+2]
            
            left_pos = df.index.get_loc(left_idx)
            head_pos = df.index.get_loc(head_idx)
            right_pos = df.index.get_loc(right_idx)
            
            # فاصله بین شانهها
            if right_pos - left_pos < self.config['min_shoulder_distance']:
                continue
            
            left_high = df['high'].loc[left_idx]
            head_high = df['high'].loc[head_idx]
            right_high = df['high'].loc[right_idx]
            
            # سر باید بالاتر از هر دو شانه باشد
            if head_high <= left_high or head_high <= right_high:
                continue
            
            # شانهها باید تقریباً همارتفاع باشند
            shoulder_diff = abs(left_high - right_high) / head_high
            if shoulder_diff > self.config['shoulder_height_tolerance']:
                continue
            
            # پیدا کردن کف بین شانه چپ و سر
            left_to_head = df.iloc[left_pos:head_pos+1]
            neck_left = left_to_head['low'].min()
            
            # پیدا کردن کف بین سر و شانه راست
            head_to_right = df.iloc[head_pos:right_pos+1]
            neck_right = head_to_right['low'].min()
            
            # خط گردن
            neckline_level = (neck_left + neck_right) / 2
            neckline_slope = (neck_right - neck_left) / (right_pos - left_pos)
            
            # محاسبه امتیاز
            score = self.score_head_shoulders_bearish(
                df, left_high, head_high, right_high, 
                neck_left, neck_right, left_pos, head_pos, right_pos
            )
            
            if score >= self.config['min_score']:
                return {
                    'type': 'bearish',
                    'left_shoulder_idx': left_pos,
                    'head_idx': head_pos,
                    'right_shoulder_idx': right_pos,
                    'left_shoulder_price': left_high,
                    'head_price': head_high,
                    'right_shoulder_price': right_high,
                    'neckline_level': neckline_level,
                    'neckline_slope': neckline_slope,
                    'score': score,
                }
        
        return None
    
    def find_head_shoulders_bullish(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        تشخیص الگوی سر و شانه کف (Bullish)
        """
        swing_high, swing_low = self.find_swing_points(df, self.config['swing_lookback'])
        
        swing_low_indices = df.index[swing_low].tolist()
        
        if len(swing_low_indices) < 3:
            return None
        
        for i in range(len(swing_low_indices) - 2):
            left_idx = swing_low_indices[i]
            head_idx = swing_low_indices[i+1]
            right_idx = swing_low_indices[i+2]
            
            left_pos = df.index.get_loc(left_idx)
            head_pos = df.index.get_loc(head_idx)
            right_pos = df.index.get_loc(right_idx)
            
            if right_pos - left_pos < self.config['min_shoulder_distance']:
                continue
            
            left_low = df['low'].loc[left_idx]
            head_low = df['low'].loc[head_idx]
            right_low = df['low'].loc[right_idx]
            
            # سر باید پایینتر از هر دو شانه باشد
            if head_low >= left_low or head_low >= right_low:
                continue
            
            # شانهها باید تقریباً همارتفاع باشند
            shoulder_diff = abs(left_low - right_low) / head_low
            if shoulder_diff > self.config['shoulder_height_tolerance']:
                continue
            
            # پیدا کردن سقف بین شانه چپ و سر
            left_to_head = df.iloc[left_pos:head_pos+1]
            neck_left = left_to_head['high'].max()
            
            # پیدا کردن سقف بین سر و شانه راست
            head_to_right = df.iloc[head_pos:right_pos+1]
            neck_right = head_to_right['high'].max()
            
            neckline_level = (neck_left + neck_right) / 2
            neckline_slope = (neck_right - neck_left) / (right_pos - left_pos)
            
            score = self.score_head_shoulders_bullish(
                df, left_low, head_low, right_low,
                neck_left, neck_right, left_pos, head_pos, right_pos
            )
            
            if score >= self.config['min_score']:
                return {
                    'type': 'bullish',
                    'left_shoulder_idx': left_pos,
                    'head_idx': head_pos,
                    'right_shoulder_idx': right_pos,
                    'left_shoulder_price': left_low,
                    'head_price': head_low,
                    'right_shoulder_price': right_low,
                    'neckline_level': neckline_level,
                    'neckline_slope': neckline_slope,
                    'score': score,
                }
        
        return None
    
    def score_head_shoulders_bearish(self, df, left_high, head_high, right_high, 
                                      neck_left, neck_right, left_pos, head_pos, right_pos):
        """امتیازدهی الگوی سقف"""
        score = 0
        
        # تقارن شانهها (۲۵ نمره)
        symmetry = 1 - abs(left_high - right_high) / head_high
        score += symmetry * 25
        
        # ارتفاع سر نسبت به شانهها (۲۰ نمره)
        head_height = (head_high - max(left_high, right_high)) / head_high
        score += min(head_height * 200, 20)
        
        # شیب خط گردن (۱۵ نمره)
        neckline_flatness = 1 - abs(neck_right - neck_left) / neck_left
        score += max(0, neckline_flatness) * 15
        
        # حجم شانه چپ باید بیشتر از شانه راست باشد (۲۰ نمره)
        left_volume = df['volume'].iloc[left_pos-3:left_pos+3].mean()
        right_volume = df['volume'].iloc[right_pos-3:right_pos+3].mean()
        if left_volume > right_volume:
            score += 20
        else:
            score += 10
        
        # فاصله مناسب بین شانهها (۲۰ نمره)
        distance = right_pos - left_pos
        ideal_distance = 40  # حدود ۴۰ کندل
        distance_score = max(0, 1 - abs(distance - ideal_distance) / ideal_distance)
        score += distance_score * 20
        
        return score
    
    def score_head_shoulders_bullish(self, df, left_low, head_low, right_low,
                                      neck_left, neck_right, left_pos, head_pos, right_pos):
        """امتیازدهی الگوی کف"""
        score = 0
        
        # تقارن شانهها (۲۵ نمره)
        symmetry = 1 - abs(left_low - right_low) / head_low
        score += symmetry * 25
        
        # عمق سر نسبت به شانهها (۲۰ نمره)
        head_depth = (min(left_low, right_low) - head_low) / head_low
        score += min(head_depth * 200, 20)
        
        # شیب خط گردن (۱۵ نمره)
        neckline_flatness = 1 - abs(neck_right - neck_left) / neck_left
        score += max(0, neckline_flatness) * 15
        
        # حجم شانه چپ باید بیشتر از شانه راست باشد (۲۰ نمره)
        left_volume = df['volume'].iloc[left_pos-3:left_pos+3].mean()
        right_volume = df['volume'].iloc[right_pos-3:right_pos+3].mean()
        if left_volume > right_volume:
            score += 20
        else:
            score += 10
        
        # فاصله مناسب (۲۰ نمره)
        distance = right_pos - left_pos
        ideal_distance = 40
        distance_score = max(0, 1 - abs(distance - ideal_distance) / ideal_distance)
        score += distance_score * 20
        
        return score
    
    def generate_signals(self, df: pd.DataFrame, df_1h: pd.DataFrame = None) -> pd.DataFrame:
        """
        تولید سیگنالها
        """
        # حجم
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_len']).mean()
        df['volume_breakout'] = df['volume'] > df['volume_ma'] * self.config['volume_breakout_multiplier']
        
        # ATR
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.config['atr_len'])
        
        # تأیید تایمفریم بالاتر
        if df_1h is not None and len(df_1h) > 0:
            ema_20_1h = df_1h['close'].ewm(span=20).mean()
            ema_50_1h = df_1h['close'].ewm(span=50).mean()
            hourly_bullish = ema_20_1h.iloc[-1] > ema_50_1h.iloc[-1]
            hourly_bearish = ema_20_1h.iloc[-1] < ema_50_1h.iloc[-1]
        else:
            hourly_bullish = True
            hourly_bearish = True
        
        # سیگنالها
        df['bull_signal'] = False
        df['bear_signal'] = False
        df['pattern_score'] = 0.0
        df['pattern_type'] = ''
        
        # بررسی الگو در هر کندل
        for i in range(50, len(df)):
            # بررسی الگوی سر و شانه روی دادههای تا کندل i
            df_window = df.iloc[:i+1]
            
            # الگوی سقف (Bearish)
            bearish_pattern = self.find_head_shoulders_bearish(df_window)
            if bearish_pattern and hourly_bearish:
                # شکست خط گردن
                neckline = bearish_pattern['neckline_level']
                if df['close'].iloc[i] < neckline and df['volume_breakout'].iloc[i]:
                    df.loc[df.index[i], 'bear_signal'] = True
                    df.loc[df.index[i], 'pattern_score'] = bearish_pattern['score']
                    df.loc[df.index[i], 'pattern_type'] = 'head_shoulders_bearish'
            
            # الگوی کف (Bullish)
            bullish_pattern = self.find_head_shoulders_bullish(df_window)
            if bullish_pattern and hourly_bullish:
                neckline = bullish_pattern['neckline_level']
                if df['close'].iloc[i] > neckline and df['volume_breakout'].iloc[i]:
                    df.loc[df.index[i], 'bull_signal'] = True
                    df.loc[df.index[i], 'pattern_score'] = bullish_pattern['score']
                    df.loc[df.index[i], 'pattern_type'] = 'head_shoulders_bullish'
        
        # حد ضرر و سود
        df['long_stop'] = df['close'] - df['atr'] * self.config['atr_mult_sl']
        df['short_stop'] = df['close'] + df['atr'] * self.config['atr_mult_sl']
        df['long_tp'] = df['close'] + df['atr'] * self.config['atr_mult_tp']
        df['short_tp'] = df['close'] - df['atr'] * self.config['atr_mult_tp']
        df['rr_ratio'] = self.config['atr_mult_tp'] / self.config['atr_mult_sl']
        
        return df
