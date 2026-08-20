from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseWalletClustering(ABC):
    @abstractmethod
    def cluster_wallets(self, wallet_features: List[Dict[str, Any]]) -> List[List[str]]:
        ...
