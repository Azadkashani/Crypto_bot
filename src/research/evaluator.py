from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.core.config import settings

def parse_horizons(horizons_str: str) -> List[Tuple[str, timedelta]]:
    mapping = {
        '1m': timedelta(minutes=1),
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '4h': timedelta(hours=4),
        '12h': timedelta(hours=12),
        '24h': timedelta(hours=24),
    }
    horizons = []
    for part in horizons_str.split(','):
        part = part.strip()
        if part in mapping:
            horizons.append((part, mapping[part]))
        else:
            raise ValueError(f"Unknown horizon: {part}")
    return horizons

def find_entry_price(candles: pd.DataFrame, signal_time: datetime) -> Optional[float]:
    """Deterministic entry price: first candle after signal_time open."""
    after = candles[candles['timestamp'] > signal_time]
    if after.empty:
        return None
    return after.iloc[0]['open']

def find_future_price(candles: pd.DataFrame, signal_time: datetime, horizon_delta: timedelta) -> Optional[float]:
    target_time = signal_time + horizon_delta
    future_candles = candles[candles['timestamp'] >= target_time]
    if future_candles.empty:
        return None
    return future_candles.iloc[0]['close']  # close of first candle at/after horizon

def compute_mfe_mae(candles: pd.DataFrame, entry_time: datetime, entry_price: float, horizon_delta: timedelta, direction: str) -> Tuple[Optional[float], Optional[float]]:
    """Returns MFE and MAE as percentage (positive numbers)."""
    end_time = entry_time + horizon_delta
    window = candles[(candles['timestamp'] > entry_time) & (candles['timestamp'] <= end_time)]
    if window.empty:
        return None, None
    if direction == 'LONG':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = max(0, (max_high - entry_price) / entry_price * 100)
        mae = max(0, (entry_price - min_low) / entry_price * 100)
    elif direction == 'SHORT':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = max(0, (entry_price - min_low) / entry_price * 100)
        mae = max(0, (max_high - entry_price) / entry_price * 100)
    else:
        mfe, mae = None, None
    return mfe, mae

def evaluate_signal(signal: Dict[str, Any], price_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    """
    Evaluate a single signal for all horizons.
    signal: dict with keys: token, chain, timestamp, direction, signal_score, confidence, etc.
    price_data: dict token -> DataFrame with columns: timestamp, open, high, low, close
    Returns list of result dicts for each horizon.
    """
    token = signal['token']
    direction = signal.get('direction')
    if direction not in ['LONG', 'SHORT']:
        return []

    candles = price_data.get(token)
    if candles is None or candles.empty:
        return []

    signal_time = signal['timestamp']
    entry_price = find_entry_price(candles, signal_time)
    if entry_price is None or entry_price <= 0:
        return []

    horizons = parse_horizons(settings.backtest_horizons)
    results = []
    for horizon_name, horizon_delta in horizons:
        future_price = find_future_price(candles, signal_time, horizon_delta)
        if future_price is None:
            continue
        if direction == 'LONG':
            return_pct = (future_price - entry_price) / entry_price * 100
        else:
            return_pct = (entry_price - future_price) / entry_price * 100

        # Outcome
        threshold = settings.backtest_neutral_threshold_pct
        if return_pct > threshold:
            outcome = 'WIN'
        elif return_pct < -threshold:
            outcome = 'LOSS'
        else:
            outcome = 'NEUTRAL'

        # MFE/MAE
        entry_time = candles[candles['timestamp'] > signal_time].iloc[0]['timestamp']
        mfe, mae = compute_mfe_mae(candles, entry_time, entry_price, horizon_delta, direction)

        results.append({
            'signal': signal,
            'token': token,
            'chain': signal.get('chain', 'ethereum'),
            'signal_timestamp': signal_time,
            'direction': direction,
            'signal_score': signal.get('signal_score'),
            'confidence': signal.get('confidence'),
            'entry_price': entry_price,
            'horizon': horizon_name,
            'future_price': future_price,
            'return_pct': return_pct,
            'outcome': outcome,
            'mfe': mfe,
            'mae': mae,
        })
    return results
