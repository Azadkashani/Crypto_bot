#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel}")

# جایگزینی کامل metrics.py بدون وابستگی به scipy
write("src/research/metrics.py", r'''
from typing import List, Dict, Any, Tuple
import numpy as np

def wilson_interval(wins: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson confidence interval for win rate."""
    if total == 0:
        return (0.0, 0.0)
    p = wins / total
    denominator = 1 + z**2 / total
    centre_adjusted = p + z**2 / (2 * total)
    adjusted_interval = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total)
    lower = (centre_adjusted - adjusted_interval) / denominator
    upper = (centre_adjusted + adjusted_interval) / denominator
    return (max(0, lower), min(1, upper))

def compute_basic_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {
            'total_signals': 0,
            'wins': 0,
            'losses': 0,
            'neutral': 0,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'median_return': 0.0,
            'profit_factor': 0.0,
            'best_return': 0.0,
            'worst_return': 0.0,
            'avg_mfe': 0.0,
            'avg_mae': 0.0,
            'sample_size': 0,
            'wilson_lower': 0.0,
            'wilson_upper': 0.0,
        }
    returns = [r['return_pct'] for r in results if r.get('return_pct') is not None]
    outcomes = [r['outcome'] for r in results if r.get('outcome')]
    wins = outcomes.count('WIN')
    losses = outcomes.count('LOSS')
    neutral = outcomes.count('NEUTRAL')
    total = len(results)
    win_rate = wins / total if total > 0 else 0.0
    avg_return = np.mean(returns) if returns else 0.0
    median_return = np.median(returns) if returns else 0.0
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = -sum(r for r in returns if r < 0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    best_return = max(returns) if returns else 0.0
    worst_return = min(returns) if returns else 0.0
    mfes = [r['mfe'] for r in results if r.get('mfe') is not None]
    maes = [r['mae'] for r in results if r.get('mae') is not None]
    avg_mfe = np.mean(mfes) if mfes else 0.0
    avg_mae = np.mean(maes) if maes else 0.0
    wilson_lower, wilson_upper = wilson_interval(wins, total)
    return {
        'total_signals': total,
        'wins': wins,
        'losses': losses,
        'neutral': neutral,
        'win_rate': win_rate * 100,
        'avg_return': avg_return,
        'median_return': median_return,
        'profit_factor': profit_factor,
        'best_return': best_return,
        'worst_return': worst_return,
        'avg_mfe': avg_mfe,
        'avg_mae': avg_mae,
        'sample_size': total,
        'wilson_lower': wilson_lower * 100,
        'wilson_upper': wilson_upper * 100,
    }

def filter_by_score(results: List[Dict[str, Any]], min_score: float = None, max_score: float = None) -> List[Dict[str, Any]]:
    filtered = results
    if min_score is not None:
        filtered = [r for r in filtered if r.get('signal_score', 0) >= min_score]
    if max_score is not None:
        filtered = [r for r in filtered if r.get('signal_score', 0) <= max_score]
    return filtered

def filter_by_confidence(results: List[Dict[str, Any]], min_conf: float = None, max_conf: float = None) -> List[Dict[str, Any]]:
    filtered = results
    if min_conf is not None:
        filtered = [r for r in filtered if r.get('confidence', 0) >= min_conf]
    if max_conf is not None:
        filtered = [r for r in filtered if r.get('confidence', 0) <= max_conf]
    return filtered

def filter_by_direction(results: List[Dict[str, Any]], direction: str) -> List[Dict[str, Any]]:
    return [r for r in results if r.get('direction') == direction]

def score_bucket(score: float) -> str:
    if score < 50:
        return '0-49'
    elif score < 60:
        return '50-59'
    elif score < 70:
        return '60-69'
    elif score < 80:
        return '70-79'
    elif score < 90:
        return '80-89'
    else:
        return '90-100'

def compute_score_buckets(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    buckets = {}
    for r in results:
        bucket = score_bucket(r.get('signal_score', 0))
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append(r)
    output = {}
    for bucket, bucket_results in buckets.items():
        stats = compute_basic_stats(bucket_results)
        output[bucket] = stats
    return output

def compute_confidence_buckets(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    buckets = {}
    for r in results:
        bucket = score_bucket(r.get('confidence', 0))
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append(r)
    output = {}
    for bucket, bucket_results in buckets.items():
        stats = compute_basic_stats(bucket_results)
        output[bucket] = stats
    return output

def compute_horizon_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    horizons = {}
    for r in results:
        h = r['horizon']
        if h not in horizons:
            horizons[h] = []
        horizons[h].append(r)
    output = {}
    for h, h_results in horizons.items():
        output[h] = compute_basic_stats(h_results)
    return output

def compute_direction_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    directions = {}
    for r in results:
        d = r['direction']
        if d not in directions:
            directions[d] = []
        directions[d].append(r)
    output = {}
    for d, d_results in directions.items():
        output[d] = compute_basic_stats(d_results)
    return output
''')

print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: remove scipy dependency from metrics"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and pushed.")
