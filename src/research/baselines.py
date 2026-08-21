from typing import List, Dict, Any
import random
from datetime import datetime
from src.research.evaluator import evaluate_signal

def random_baseline(signals: List[Dict[str, Any]], price_data: Dict[str, Any], iterations: int = 100) -> Dict[str, Any]:
    """
    For each signal timestamp, generate a random direction (LONG/SHORT) and evaluate.
    Returns average win rate and average return across iterations.
    """
    if not signals:
        return {'avg_win_rate': 0.0, 'avg_return': 0.0, 'iterations': 0}
    all_win_rates = []
    all_returns = []
    for i in range(iterations):
        fake_signals = []
        for sig in signals:
            fake_sig = dict(sig)
            fake_sig['direction'] = random.choice(['LONG', 'SHORT'])
            fake_signals.append(fake_sig)
        results = []
        for sig in fake_signals:
            results.extend(evaluate_signal(sig, price_data))
        if results:
            wins = sum(1 for r in results if r['outcome'] == 'WIN')
            total = len(results)
            win_rate = wins / total if total > 0 else 0
            avg_return = sum(r['return_pct'] for r in results) / total
            all_win_rates.append(win_rate)
            all_returns.append(avg_return)
    avg_win_rate = sum(all_win_rates) / len(all_win_rates) if all_win_rates else 0
    avg_return = sum(all_returns) / len(all_returns) if all_returns else 0
    return {
        'avg_win_rate': avg_win_rate * 100,
        'avg_return': avg_return,
        'iterations': iterations,
    }
