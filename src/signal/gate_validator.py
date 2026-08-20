from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseGateValidator(ABC):
    @abstractmethod
    def is_futures_available(self, token: str) -> bool:
        ...
    @abstractmethod
    def get_market_data(self, token: str) -> Dict[str, Any]:
        ...
