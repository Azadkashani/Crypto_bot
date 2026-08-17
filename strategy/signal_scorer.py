"""
سیستم امتیازدهی سیگنالهای معاملاتی
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalScorer:
    """
    سیستم امتیازدهی سیگنالها بر اساس معیارهای مختلف
    """
    
    def __init__(self, config: Dict = None):
        """
        مقداردهی اولیه سیستم امتیازدهی
        
        Parameters:
        -----------
        config : Dict
            تنظیمات امتیازدهی
        """
        self.config = {
            'weights': {
                'timeframe_alignment': 0.25,    # هم‌جهتی تایم‌فریم‌ها
                'market_sentiment': 0.15,       # احساسات بازار
                'risk_reward_ratio': 0.20,      # نسبت ریسک به ریوارد
                'news_impact': 0.15,            # تاثیر اخبار
                'indicator_confirmation': 0.15, # تایید اندیکاتورها
                'trend_strength': 0.10,         # قدرت روند
            },
            'min_score_to_trade': 0.70,  # حداقل امتیاز ۷۰٪
        }
        
        if config:
            self.config.update(config)
    
    def score_timeframe_alignment(self, primary_trend: int, confirmation_trend: int) -> float:
        """
        امتیاز هم‌جهتی تایم‌فریم‌ها
        
        Parameters:
        -----------
        primary_trend : int
            روند در تایم‌فریم اصلی (1=صعودی, -1=نزولی)
        confirmation_trend : int
            روند در تایم‌فریم تایید (1=صعودی, -1=نزولی)
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        if primary_trend == confirmation_trend:
            return 1.0  # هم‌جهت کامل
        elif confirmation_trend == 0:
            return 0.5  # تایم‌فریم تایید خنثی
        else:
            return 0.0  # خلاف جهت
    
    def score_market_sentiment(self, fear_greed_value: int) -> float:
        """
        امتیاز احساسات بازار بر اساس Fear & Greed Index
        
        Parameters:
        -----------
        fear_greed_value : int
            مقدار شاخص ترس و طمع (0 تا 100)
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        # ترس شدید = فرصت خرید خوب
        # طمع شدید = احتمال اصلاح
        if fear_greed_value <= 25:
            return 0.8  # ترس شدید - خوب برای خرید
        elif fear_greed_value <= 40:
            return 0.7  # ترس - نسبتاً خوب
        elif fear_greed_value <= 60:
            return 0.5  # خنثی
        elif fear_greed_value <= 75:
            return 0.4  # طمع - احتیاط
        else:
            return 0.2  # طمع شدید - خطرناک
    
    def score_risk_reward(self, rr_ratio: float, min_rr: float = 2.0) -> float:
        """
        امتیاز نسبت ریسک به ریوارد
        
        Parameters:
        -----------
        rr_ratio : float
            نسبت ریسک به ریوارد
        min_rr : float
            حداقل نسبت قابل قبول
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        if rr_ratio >= min_rr * 2:
            return 1.0  # عالی
        elif rr_ratio >= min_rr:
            return 0.7  # خوب
        elif rr_ratio >= min_rr * 0.5:
            return 0.3  # ضعیف
        else:
            return 0.0  # غیرقابل قبول
    
    def score_news_impact(self, news_sentiment: str) -> float:
        """
        امتیاز تاثیر اخبار
        
        Parameters:
        -----------
        news_sentiment : str
            احساسات اخبار ('positive', 'negative', 'neutral', 'none')
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        sentiment_scores = {
            'positive': 0.8,
            'neutral': 0.5,
            'none': 0.5,
            'negative': 0.2,
        }
        return sentiment_scores.get(news_sentiment, 0.5)
    
    def score_indicator_confirmation(self, indicators: Dict) -> float:
        """
        امتیاز تایید اندیکاتورها
        
        Parameters:
        -----------
        indicators : Dict
            وضعیت اندیکاتورها
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        confirmations = 0
        total = 0
        
        # EMA تایید
        if 'ema_aligned' in indicators:
            total += 1
            if indicators['ema_aligned']:
                confirmations += 1
        
        # ADX تایید
        if 'adx_confirmed' in indicators:
            total += 1
            if indicators['adx_confirmed']:
                confirmations += 1
        
        # Bollinger تایید
        if 'bb_confirmed' in indicators:
            total += 1
            if indicators['bb_confirmed']:
                confirmations += 1
        
        # Volume تایید
        if 'volume_confirmed' in indicators:
            total += 1
            if indicators['volume_confirmed']:
                confirmations += 1
        
        if total == 0:
            return 0.5
        
        return confirmations / total
    
    def score_trend_strength(self, adx_value: float) -> float:
        """
        امتیاز قدرت روند بر اساس ADX
        
        Parameters:
        -----------
        adx_value : float
            مقدار ADX
            
        Returns:
        --------
        float
            امتیاز بین 0 تا 1
        """
        if adx_value >= 40:
            return 1.0  # روند بسیار قوی
        elif adx_value >= 30:
            return 0.8  # روند قوی
        elif adx_value >= 25:
            return 0.6  # روند متوسط
        elif adx_value >= 20:
            return 0.4  # روند ضعیف
        else:
            return 0.0  # بدون روند
    
    def calculate_total_score(self, scores: Dict) -> Dict:
        """
        محاسبه امتیاز کل
        
        Parameters:
        -----------
        scores : Dict
            امتیازهای هر بخش
            
        Returns:
        --------
        Dict
            امتیاز کل و جزئیات
        """
        total_score = 0
        details = {}
        
        for key, weight in self.config['weights'].items():
            if key in scores:
                score = scores[key]
                weighted_score = score * weight
                total_score += weighted_score
                details[key] = {
                    'raw_score': score,
                    'weight': weight,
                    'weighted_score': weighted_score,
                }
        
        return {
            'total_score': total_score,
            'details': details,
            'passed': total_score >= self.config['min_score_to_trade'],
        }
    
    def score_signal(self, signal_data: Dict) -> Dict:
        """
        امتیازدهی کامل یک سیگنال
        
        Parameters:
        -----------
        signal_data : Dict
            اطلاعات سیگنال شامل:
            - primary_trend
            - confirmation_trend
            - fear_greed_value
            - rr_ratio
            - news_sentiment
            - indicators
            - adx_value
            
        Returns:
        --------
        Dict
            نتیجه امتیازدهی کامل
        """
        # محاسبه امتیازها
        scores = {}
        
        if 'primary_trend' in signal_data and 'confirmation_trend' in signal_data:
            scores['timeframe_alignment'] = self.score_timeframe_alignment(
                signal_data['primary_trend'],
                signal_data['confirmation_trend']
            )
        
        if 'fear_greed_value' in signal_data:
            scores['market_sentiment'] = self.score_market_sentiment(
                signal_data['fear_greed_value']
            )
        
        if 'rr_ratio' in signal_data:
            scores['risk_reward_ratio'] = self.score_risk_reward(
                signal_data['rr_ratio']
            )
        
        if 'news_sentiment' in signal_data:
            scores['news_impact'] = self.score_news_impact(
                signal_data['news_sentiment']
            )
        
        if 'indicators' in signal_data:
            scores['indicator_confirmation'] = self.score_indicator_confirmation(
                signal_data['indicators']
            )
        
        if 'adx_value' in signal_data:
            scores['trend_strength'] = self.score_trend_strength(
                signal_data['adx_value']
            )
        
        # محاسبه امتیاز کل
        result = self.calculate_total_score(scores)
        
        return result
