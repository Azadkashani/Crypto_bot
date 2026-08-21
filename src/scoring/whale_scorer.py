import math
from typing import Dict, Any, List
from src.core.config import settings

def log_normalize(value: float, min_val: float = 1.0, max_val: float = 1e12) -> float:
    if value <= 0:
        return 0.0
    value = max(min_val, min(value, max_val))
    log_min = math.log10(min_val)
    log_max = math.log10(max_val)
    log_val = math.log10(value)
    normalized = (log_val - log_min) / (log_max - log_min)
    return max(0.0, min(100.0, normalized * 100.0))

def percentile_normalize(value: float, all_values: List[float]) -> float:
    if not all_values:
        return 0.0
    count = len(all_values)
    rank = sum(1 for x in all_values if x <= value)
    percentile = (rank / count) * 100.0
    return max(0.0, min(100.0, percentile))

def compute_whale_score(stats: Dict[str, Any]) -> float:
    w_volume = settings.whale_volume_weight
    w_avg = settings.whale_avg_trade_weight
    w_largest = settings.whale_largest_trade_weight
    w_activity = settings.whale_activity_weight
    w_dex = settings.whale_dex_activity_weight
    w_capital = settings.whale_capital_weight

    vol_score = log_normalize(stats.get('total_volume_usd', 0), 1, 1e12)
    avg_score = log_normalize(stats.get('average_trade_size_usd', 0), 1, 1e9)
    largest_score = log_normalize(stats.get('largest_trade_size_usd', 0), 1, 1e9)
    activity_score = log_normalize(stats.get('swap_count', 0), 1, 100000)
    dex_score = log_normalize(stats.get('unique_dexes', 0), 1, 50)
    capital_score = log_normalize(stats.get('balance_usd', 0), 1, 1e12)

    score = (
        w_volume * vol_score +
        w_avg * avg_score +
        w_largest * largest_score +
        w_activity * activity_score +
        w_dex * dex_score +
        w_capital * capital_score
    )
    return max(0.0, min(100.0, score))
