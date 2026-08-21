from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.smart_money_scorer import compute_smart_money_score
from src.smart_money.price_provider import PriceProvider
from src.core.config import settings
import math

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

class WalletPerformanceCalculator:
    def __init__(self, price_provider: PriceProvider, as_of: Optional[datetime] = None):
        self.price_provider = price_provider
        self.as_of = as_of
        self.horizons = parse_horizons(settings.smart_money_horizons)

    def _filter_buy_events(self, events: List[BuyEvent]) -> List[BuyEvent]:
        if self.as_of is None:
            return events
        return [e for e in events if e.timestamp <= self.as_of]

    def evaluate_events(self, events: List[BuyEvent]) -> Dict[str, Any]:
        filtered = self._filter_buy_events(events)
        evaluations = []
        for event in filtered:
            ev = evaluate_buy_event(event, self.price_provider, self.horizons,
                                    min_win_return_pct=settings.min_win_return_pct,
                                    as_of=self.as_of)
            evaluations.append(ev)
        return evaluations

    def compute_wallet_summary(self, wallet: str, events: List[BuyEvent]) -> Dict[str, Any]:
        evaluations = self.evaluate_events(events)
        valid_evals = [e for e in evaluations if e.evaluation_status in ['COMPLETED', 'PARTIAL']]
        if not valid_evals:
            return {
                'wallet': wallet,
                'sample_size': 0,
                'evaluated_events': 0,
                'win_rate': None,
                'average_return': None,
                'median_return': None,
                'profit_factor': None,
                'timing_accuracy': None,
                'entry_quality': None,
                'average_mfe': None,
                'average_mae': None,
                'consistency_score': None,
                'smart_money_score': 0.0,
                'smart_money_status': 'INSUFFICIENT_DATA',
                'performance_confidence': 0.0,
            }

        # Extract metrics per evaluation for each horizon
        win_rates = []
        returns = []
        for horizon_name, _ in self.horizons:
            horizon_returns = [e.returns.get(horizon_name) for e in valid_evals if e.returns.get(horizon_name) is not None]
            horizon_wins = [e.win_flags.get(horizon_name) for e in valid_evals if e.win_flags.get(horizon_name) is not None]
            if horizon_returns:
                returns.extend(horizon_returns)
            if horizon_wins:
                win_rate_horizon = sum(horizon_wins) / len(horizon_wins) * 100
                win_rates.append(win_rate_horizon)

        if not returns:
            return {
                'wallet': wallet,
                'sample_size': 0,
                'evaluated_events': 0,
                'win_rate': None,
                'average_return': None,
                'median_return': None,
                'profit_factor': None,
                'timing_accuracy': None,
                'entry_quality': None,
                'average_mfe': None,
                'average_mae': None,
                'consistency_score': None,
                'smart_money_score': 0.0,
                'smart_money_status': 'INSUFFICIENT_DATA',
                'performance_confidence': 0.0,
            }

        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0
        avg_return = sum(returns) / len(returns) if returns else 0.0
        median_return = sorted(returns)[len(returns)//2] if returns else 0.0

        # Profit factor: gross profit / gross loss across all horizons
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = sum(-r for r in returns if r < 0)
        if gross_loss == 0:
            profit_factor = float('inf') if gross_profit > 0 else 0.0
        else:
            profit_factor = gross_profit / gross_loss

        # MFE/MAE averages
        mfes = []
        maes = []
        for e in valid_evals:
            for horizon_name, _ in self.horizons:
                mfe_val = e.mfe.get(horizon_name)
                mae_val = e.mae.get(horizon_name)
                if mfe_val is not None:
                    mfes.append(mfe_val)
                if mae_val is not None:
                    maes.append(mae_val)

        avg_mfe = sum(mfes) / len(mfes) if mfes else 0.0
        avg_mae = sum(maes) / len(maes) if maes else 0.0

        # Timing accuracy: simplification: percentage of events with positive return at earliest horizon (e.g., 1h)
        # We'll use win rate at 1h if available, else average win rate.
        # Entry quality: simplified as avg return at 5m? We'll use avg return for all horizons.
        timing_accuracy = avg_win_rate
        entry_quality = avg_return

        # Consistency: 100 - stddev of returns (simplified)
        if len(returns) > 1:
            mean = sum(returns)/len(returns)
            variance = sum((r - mean)**2 for r in returns) / (len(returns)-1)
            stddev = math.sqrt(variance)
            consistency_score = max(0.0, 100.0 - stddev)
        else:
            consistency_score = 0.0

        # MFE/MAE ratio score: (avg_mfe / (avg_mfe + avg_mae)) * 100 if both >0
        if avg_mfe + avg_mae > 0:
            mfe_mae_score = (avg_mfe / (avg_mfe + avg_mae)) * 100
        else:
            mfe_mae_score = 50.0

        # Compute Smart Money Score using compute_smart_money_score
        smart_result = compute_smart_money_score(
            win_rate=avg_win_rate,
            avg_return=avg_return,
            profit_factor=profit_factor,
            timing_accuracy=timing_accuracy,
            entry_quality=entry_quality,
            mfe_mae_score=mfe_mae_score,
            consistency_score=consistency_score,
            sample_size=len(valid_evals),
            min_events=settings.min_smart_money_events
        )

        return {
            'wallet': wallet,
            'sample_size': len(valid_evals),
            'evaluated_events': len(valid_evals),
            'win_rate': avg_win_rate,
            'average_return': avg_return,
            'median_return': median_return,
            'profit_factor': profit_factor,
            'timing_accuracy': timing_accuracy,
            'entry_quality': entry_quality,
            'average_mfe': avg_mfe,
            'average_mae': avg_mae,
            'consistency_score': consistency_score,
            'smart_money_score': smart_result['score'],
            'smart_money_status': smart_result['status'],
            'performance_confidence': smart_result['confidence'],
        }
