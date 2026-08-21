from typing import Dict, Any
from src.core.config import settings
from src.scoring.whale_scorer import compute_whale_score
from src.detection.excluded_addresses import ExcludedAddressRegistry

class WhaleDetector:
    def __init__(self, registry: ExcludedAddressRegistry):
        self.registry = registry

    def is_candidate(self, stats: Dict[str, Any]) -> bool:
        if stats['total_volume_usd'] >= settings.whale_min_total_volume_usd: return True
        if stats['average_trade_size_usd'] >= settings.whale_min_avg_trade_usd: return True
        if stats['largest_trade_size_usd'] >= settings.whale_min_largest_trade_usd: return True
        if stats['buy_volume_usd'] >= settings.whale_min_buy_volume_usd: return True
        if stats['swap_count'] >= settings.whale_min_swap_count: return True
        return False

    def is_excluded(self, address: str) -> bool:
        return self.registry.is_excluded(address)

    def detect_whale(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        address = stats['address']
        if self.is_excluded(address):
            return {'is_whale': False, 'is_candidate': False, 'status': 'EXCLUDED',
                    'whale_score': None, 'exclusion_reason': self.registry.get_category(address)}

        if not self.is_candidate(stats):
            return {'is_whale': False, 'is_candidate': False,
                    'status': 'ACTIVE' if stats['swap_count'] > 0 else 'UNKNOWN',
                    'whale_score': compute_whale_score(stats), 'exclusion_reason': None}

        whale_score = compute_whale_score(stats)
        if whale_score >= settings.whale_score_threshold_whale:
            return {'is_whale': True, 'is_candidate': True, 'status': 'WHALE',
                    'whale_score': whale_score, 'exclusion_reason': None}
        elif whale_score >= settings.whale_score_threshold_candidate:
            return {'is_whale': False, 'is_candidate': True, 'status': 'WHALE_CANDIDATE',
                    'whale_score': whale_score, 'exclusion_reason': None}
        else:
            return {'is_whale': False, 'is_candidate': True, 'status': 'ACTIVE',
                    'whale_score': whale_score, 'exclusion_reason': None}
