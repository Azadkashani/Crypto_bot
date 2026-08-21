from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

class MarketConfirmation:
    def __init__(self):
        pass

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """df must have columns: timestamp, open, high, low, close, volume.
        Index sorted ascending by timestamp.
        Returns df with indicators added."""
        df = df.copy()
        # EMA
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # RSI 14
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # MACD (12,26,9)
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # ATR (14)
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(window=14).mean()

        # Volume ratio: current volume vs 20-period average
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']

        # Momentum: close vs close 10 periods ago
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1

        # Volatility: standard deviation of returns over 20 periods
        df['returns'] = df['close'].pct_change()
        df['volatility_20'] = df['returns'].rolling(window=20).std()

        return df

    def score_market(self, df: pd.DataFrame, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Score the market at a given timestamp (last row <= timestamp).
        Returns dict with score (0-100), direction ('bullish','bearish','neutral'), and components."""
        if timestamp is not None:
            df = df[df['timestamp'] <= timestamp]
        if df.empty:
            return {
                'score': 50.0,
                'direction': 'neutral',
                'components': {},
                'confidence': 0.0,
            }

        df = self.compute_indicators(df)
        last = df.iloc[-1]

        # Basic conditions
        trend_bull = last['close'] > last['ema_50'] > last['ema_200']
        trend_bear = last['close'] < last['ema_50'] < last['ema_200']
        rsi_overbought = last['rsi_14'] > 70 if not pd.isna(last['rsi_14']) else False
        rsi_oversold = last['rsi_14'] < 30 if not pd.isna(last['rsi_14']) else False
        macd_bull = last['macd'] > last['macd_signal'] if not pd.isna(last['macd']) else False
        macd_bear = last['macd'] < last['macd_signal'] if not pd.isna(last['macd']) else False
        vol_expand = last['volume_ratio'] > 1.5 if not pd.isna(last['volume_ratio']) else False
        momentum_positive = last['momentum_10'] > 0 if not pd.isna(last['momentum_10']) else False
        momentum_negative = last['momentum_10'] < 0 if not pd.isna(last['momentum_10']) else False

        # Scoring components
        trend_score = 0.0
        if trend_bull:
            trend_score = 100.0
        elif trend_bear:
            trend_score = 0.0
        else:
            trend_score = 50.0

        rsi_score = 50.0
        if rsi_overbought:
            rsi_score = 30.0  # overbought -> bearish bias
        elif rsi_oversold:
            rsi_score = 70.0  # oversold -> bullish bias
        else:
            # neutral zone, slight positive if RSI > 50
            rsi_score = 50.0 if last['rsi_14'] == 50 else (last['rsi_14'] if not pd.isna(last['rsi_14']) else 50.0)

        macd_score = 50.0
        if macd_bull:
            macd_score = 80.0
        elif macd_bear:
            macd_score = 20.0

        volume_score = 50.0
        if vol_expand:
            volume_score = 80.0  # expansion is positive in direction of trend, but we'll use neutral

        momentum_score = 50.0
        if momentum_positive:
            momentum_score = 70.0
        elif momentum_negative:
            momentum_score = 30.0

        # Simple weighted average
        score = 0.3*trend_score + 0.2*rsi_score + 0.2*macd_score + 0.15*volume_score + 0.15*momentum_score
        score = max(0.0, min(100.0, score))

        if score >= 65:
            direction = 'bullish'
        elif score <= 35:
            direction = 'bearish'
        else:
            direction = 'neutral'

        components = {
            'trend_score': trend_score,
            'rsi_score': rsi_score,
            'macd_score': macd_score,
            'volume_score': volume_score,
            'momentum_score': momentum_score,
        }

        confidence = min(100.0, 50.0 + len(df)*0.5)  # more data = more confidence

        return {
            'score': score,
            'direction': direction,
            'components': components,
            'confidence': confidence,
        }
