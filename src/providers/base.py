from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional
from src.core.constants import Chain

class BaseDataProvider(ABC):
    name: str
    chain: Chain

    @abstractmethod
    async def fetch_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def fetch_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def fetch_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def stream_blocks(self, callback: Callable[[Dict[str, Any]], None]):
        ...

    @abstractmethod
    async def stream_logs(self, topics: List[str], callback: Callable[[Dict[str, Any]], None]):
        ...

    @abstractmethod
    async def fetch_token_price(self, token: str, timestamp: int) -> float:
        ...

    @abstractmethod
    async def fetch_market_cap(self, token: str) -> float:
        ...
