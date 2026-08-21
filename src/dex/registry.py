from typing import List, Dict, Any, Optional
from src.dex.base import BaseDEXAdapter

class DEXRegistry:
    def __init__(self):
        self._adapters: Dict[str, BaseDEXAdapter] = {}

    def register(self, dex_name: str, adapter: BaseDEXAdapter):
        self._adapters[dex_name.lower()] = adapter

    def get(self, dex_name: str) -> Optional[BaseDEXAdapter]:
        return self._adapters.get(dex_name.lower())

    def detect(self, log: Dict[str, Any]) -> Optional[BaseDEXAdapter]:
        for adapter in self._adapters.values():
            if adapter.identify_swap(log):
                return adapter
        return None

    def all_adapters(self) -> List[BaseDEXAdapter]:
        return list(self._adapters.values())
