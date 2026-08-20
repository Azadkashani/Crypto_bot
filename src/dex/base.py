from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel

class DexInfo(BaseModel):
    name: str
    chain: str
    router_address: str
    factory_address: str
    pair_created_event: str
    swap_event: str

class BaseDexAdapter(ABC):
    dex_info: DexInfo

    @abstractmethod
    def parse_swap(self, log: Dict[str, Any]) -> Dict[str, Any]:
        ...
