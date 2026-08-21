from typing import Dict, Any, List
from src.research.metrics import (
    compute_basic_stats,
    compute_score_buckets,
    compute_confidence_buckets,
    compute_horizon_stats,
    compute_direction_stats,
)

def generate_report(backtest_results: List[Dict[str, Any]], baseline: Dict[str, Any] = None) -> Dict[str, Any]:
    overall = compute_basic_stats(backtest_results)
    long_stats = compute_basic_stats([r for r in backtest_results if r['direction'] == 'LONG'])
    short_stats = compute_basic_stats([r for r in backtest_results if r['direction'] == 'SHORT'])
    horizon_stats = compute_horizon_stats(backtest_results)
    score_buckets = compute_score_buckets(backtest_results)
    confidence_buckets = compute_confidence_buckets(backtest_results)

    report = {
        'overall': overall,
        'long': long_stats,
        'short': short_stats,
        'horizons': horizon_stats,
        'score_buckets': score_buckets,
        'confidence_buckets': confidence_buckets,
        'baseline': baseline,
    }
    return report

def export_to_csv(results: List[Dict[str, Any]], filename: str):
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv(filename, index=False)
    return filename
