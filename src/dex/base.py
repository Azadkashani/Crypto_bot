from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class SwapInfo(BaseModel):
    dex: str
    protocol_version: str
    pool_address: str
    sender: str
    recipient: str
    amount0_in: int
    amount1_in: int
    amount0_out: int
    amount1_out: int

class BaseDEXAdapter(ABC):
    dex_name: str
    chain: str
    protocol_version: str

    @abstractmethod
    def identify_swap(self, log: Dict[str, Any]) -> bool:
        """Check if log is a swap event from this DEX."""
        ...

    @abstractmethod
    def parse_swap(self, log: Dict[str, Any]) -> Optional[SwapInfo]:
        """Parse raw log into SwapInfo."""
        ...

    @abstractmethod
    def identify_participants(self, swap: SwapInfo, tx: Dict[str, Any]) -> Dict[str, str]:
        """Return wallet_address, router_address, pool_address, etc."""
        ...

    @abstractmethod
    def determine_direction(self, swap: SwapInfo, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return side, token_in, token_out, reasons."""
        ...
