from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.core.constants import Chain

class BlockData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    block_hash: str
    timestamp: int
    parent_hash: str
    extra_data: Optional[Dict[str, Any]] = None

class TransactionData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    block_hash: str
    transaction_hash: str
    transaction_index: int
    from_address: str
    to_address: Optional[str]
    value: int
    timestamp: int
    status: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    logs: Optional[List[Dict[str, Any]]] = None
    extra_data: Optional[Dict[str, Any]] = None

class TransferData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    transaction_hash: str
    log_index: int
    token_address: str
    from_address: str
    to_address: str
    amount: int
    token_decimals: int
    token_symbol: Optional[str] = None
    timestamp: int
    extra_data: Optional[Dict[str, Any]] = None

class SwapEventData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    transaction_hash: str
    log_index: int
    dex: str
    pair_address: str
    sender: str
    recipient: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    timestamp: int
    extra_data: Optional[Dict[str, Any]] = None

class BaseBlockchainAdapter(ABC):
    chain: Chain
    network: str

    @abstractmethod
    async def get_latest_block_number(self) -> int:
        ...

    @abstractmethod
    async def get_block_by_number(self, block_number: int) -> BlockData:
        ...

    @abstractmethod
    async def get_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[TransactionData]:
        ...

    @abstractmethod
    async def get_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[TransferData]:
        ...

    @abstractmethod
    async def get_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[SwapEventData]:
        ...

    @abstractmethod
    async def get_wallet_balance(self, address: str) -> float:
        ...

    @abstractmethod
    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def is_contract(self, address: str) -> bool:
        ...
