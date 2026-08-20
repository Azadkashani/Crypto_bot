from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseNotifier(ABC):
    @abstractmethod
    def send(self, message: str, data: Dict[str, Any] = None) -> bool:
        ...
