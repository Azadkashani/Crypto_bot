from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

class EntryTiming:
    def __init__(self):
        pass

    def compute_score(self, df: pd.DataFrame, timestamp: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
        """Returns entry timing score (0-100) and label."""
        if timestamp is not None:
            df = df[df['timestamp'] <= timestamp]
        if df.empty:
            return {'score': 50.0, 'label': 'UNKNOWN', 'reasons': ['NO_DATA']}

        # Use last row
        last = df.iloc[-1]
        reasons = []

        # Price vs EMAs
        if 'ema_20' not in df.columns:
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        if 'ema_50' not in df.columns:
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        last = df.iloc[-1]

        price = last['close']
        ema20 = last['ema_20']
        ema50 = last['ema_50']

        distance_to_ema20_pct = ((price - ema20) / ema20) * 100 if ema20 else 0
        distance_to_ema50_pct = ((price - ema50) / ema50) * 100 if ema50 else 0

        # RSI
        if 'rsi_14' not in df.columns:
            delta = df['close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
            last = df.iloc[-1]

        rsi = last['rsi_14'] if not pd.isna(last['rsi_14']) else 50

        # Overbought/Oversold
        if rsi > 70:
            reasons.append('OVERBOUGHT')
            overbought_penalty = 20
        elif rsi < 30:
            reasons.append('OVERSOLD')
            overbought_bonus = 20
        else:
            overbought_penalty = 0
            overbought_bonus = 0

        # Momentum
        if 'momentum_10' not in df.columns:
            df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
            last = df.iloc[-1]
        momentum = last['momentum_10'] if not pd.isna(last['momentum_10']) else 0
        if momentum > 0.03:
            reasons.append('STRONG_MOMENTUM')
            momentum_score = 80
        elif momentum < -0.03:
            reasons.append('NEGATIVE_MOMENTUM')
            momentum_score = 20
        else:
            momentum_score = 50

        # ATR (volatility normalization)
        if 'atr_14' not in df.columns:
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr_14'] = tr.rolling(window=14).mean()
            last = df.iloc[-1]
        atr = last['atr_14'] if not pd.isna(last['atr_14']) else 0
        # Normalize ATR as percentage of price
        atr_pct = (atr / price) * 100 if price else 0

        # Score calculation
        base_score = 50.0

        # Distance from EMA: if price close to EMA, good; if extended, bad for new entry
        if abs(distance_to_ema20_pct) < 1.0:
            base_score += 15
        elif abs(distance_to_ema20_pct) > 5.0:
            base_score -= 15

        if abs(distance_to_ema50_pct) < 2.0:
            base_score += 10
        elif abs(distance_to_ema50_pct) > 8.0:
            base_score -= 10

        # RSI effect
        if rsi > 70:
            base_score -= overbought_penalty if 'overbought_penalty' in locals() else 20
        elif rsi < 30:
            base_score += overbought_bonus if 'overbought_bonus' in locals() else 20

        # Momentum effect
        base_score += (momentum_score - 50) * 0.2

        # ATR effect: high volatility reduces score for entry
        if atr_pct > 5:
            base_score -= 10
        elif atr_pct < 1:
            base_score += 5

        score = max(0, min(100, base_score))

        # Label
        if score >= 75:
            label = 'GOOD_ENTRY'
        elif score >= 55:
            label = 'EARLY_ENTRY'
        elif score >= 35:
            label = 'LATE_ENTRY'
        elif score >= 20:
            label = 'EXTENDED'
        else:
            label = 'UNFAVORABLE'

        return {'score': score, 'label': label, 'reasons': reasons}
