from typing import Dict, Any, List, Optional
from datetime import datetime
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator
from src.detection.whale_detector import WhaleDetector

class WalletProfileBuilder:
    def __init__(self, swaps: List[NormalizedSwap], excluded_registry, as_of: Optional[datetime] = None):
        self.aggregator = WalletAggregator(swaps, as_of)
        self.detector = WhaleDetector(excluded_registry)

    def build_profiles(self) -> Dict[str, Dict[str, Any]]:
        stats = self.aggregator.aggregate()
        profiles = {}
        for addr, wallet_stats in stats.items():
            detection = self.detector.detect_whale(wallet_stats)
            profiles[addr] = {**wallet_stats,
                              'whale_score': detection['whale_score'],
                              'status': detection['status'],
                              'is_whale': detection['is_whale'],
                              'is_candidate': detection['is_candidate'],
                              'exclusion_reason': detection['exclusion_reason']}
        return profiles
