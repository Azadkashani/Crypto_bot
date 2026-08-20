from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTokenMetadata(ABC):
    @abstractmethod
    def get_metadata(self, token: str, chain: str) -> Dict[str, Any]:
        ...
