from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseMarketConfirmation(ABC):
    @abstractmethod
    def confirm(self, token: str, context: Dict[str, Any]) -> bool:
        ...
