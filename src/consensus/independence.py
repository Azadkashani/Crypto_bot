from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseIndependenceCalculator(ABC):
    @abstractmethod
    def independent_wallets(self, whale_events: List[Dict[str, Any]]) -> int:
        ...
