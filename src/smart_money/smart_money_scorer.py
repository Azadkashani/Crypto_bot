from typing import Dict, Any, Optional
from src.core.config import settings
import math

def _normalize_return_pct(r: Optional[float]) -> float:
    """Map percentage return to a 0-100 score. 0% -> 0, 50%+ -> 100 (capped)."""
    if r is None:
        return 0.0
    # Map 0% to 0, 50% to 100 linearly; cap at 100.
    return max(0.0, min(100.0, r * 2.0))

def _profit_factor_score(pf: Optional[float]) -> float:
    if pf is None or pf <= 0:
        return 0.0
    if pf == float('inf'):
        return 100.0
    # Log scale between 0.5 and 3.0 -> 0-100
    log_pf = math.log(pf)
    log_min = math.log(0.5)
    log_max = math.log(3.0)
    normalized = (log_pf - log_min) / (log_max - log_min)
    return max(0.0, min(100.0, normalized * 100.0))

def compute_smart_money_score(
    win_rate: Optional[float],
    avg_return: Optional[float],
    profit_factor: Optional[float],
    timing_accuracy: Optional[float],
    entry_quality: Optional[float],
    mfe_mae_score: Optional[float],
    consistency_score: Optional[float],
    sample_size: int,
    min_events: int = None
) -> Dict[str, Any]:
    if min_events is None:
        min_events = settings.min_smart_money_events

    # تبدیل avg_return به امتیاز 0-100
    avg_return_score = _normalize_return_pct(avg_return)

    weights = {
        'win_rate': settings.smart_money_weight_win_rate,
        'avg_return': settings.smart_money_weight_avg_return,
        'profit_factor': settings.smart_money_weight_profit_factor,
        'timing': settings.smart_money_weight_timing,
        'entry_quality': settings.smart_money_weight_entry_quality,
        'mfe_mae': settings.smart_money_weight_mfe_mae,
        'consistency': settings.smart_money_weight_consistency,
    }

    win_score = win_rate if win_rate is not None else 0.0
    pf_score = _profit_factor_score(profit_factor)
    timing_score = timing_accuracy if timing_accuracy is not None else 0.0
    entry_quality_score = entry_quality if entry_quality is not None else 0.0
    mfe_mae_score = mfe_mae_score if mfe_mae_score is not None else 0.0
    consistency_score = consistency_score if consistency_score is not None else 0.0

    raw_score = (
        weights['win_rate'] * win_score +
        weights['avg_return'] * avg_return_score +
        weights['profit_factor'] * pf_score +
        weights['timing'] * timing_score +
        weights['entry_quality'] * entry_quality_score +
        weights['mfe_mae'] * mfe_mae_score +
        weights['consistency'] * consistency_score
    )

    # Confidence adjustment based on sample size
    if sample_size < min_events:
        confidence_factor = sample_size / min_events
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100
        # اگر داده کافی نیست، وضعیت INSUFFICIENT_DATA برگردانده می‌شود
        return {
            'score': max(0.0, min(100.0, final_score)),
            'status': 'INSUFFICIENT_DATA',
            'confidence': max(0.0, min(100.0, performance_confidence)),
            'raw_score': raw_score,
            'sample_size': sample_size,
        }
    else:
        confidence_factor = min(1.0, math.sqrt(sample_size / min_events))
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100

    # تعیین وضعیت بر اساس final_score
    if final_score < settings.score_poor_threshold:
        status = "POOR"
    elif final_score < settings.score_weak_threshold:
        status = "WEAK"
    elif final_score < settings.score_average_threshold:
        status = "AVERAGE"
    elif final_score < settings.score_good_threshold:
        status = "GOOD"
    elif final_score < settings.score_strong_threshold:
        status = "STRONG"
    else:
        status = "EXCEPTIONAL"

    return {
        'score': max(0.0, min(100.0, final_score)),
        'status': status,
        'confidence': max(0.0, min(100.0, performance_confidence)),
        'raw_score': raw_score,
        'sample_size': sample_size,
    }
