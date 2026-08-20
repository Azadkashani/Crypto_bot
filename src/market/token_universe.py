from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseTokenUniverse(ABC):
    @abstractmethod
    def get_candidate_tokens(self) -> List[str]:
        ...
    @abstractmethod
    def filter_tokens(self, tokens: List[str], filters: Dict[str, Any]) -> List[str]:
        ...
