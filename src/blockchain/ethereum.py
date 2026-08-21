from typing import List, Optional, Dict, Any
from src.blockchain.base import BaseBlockchainAdapter, BlockData, TransactionData, TransferData, SwapEventData
from src.providers.base import BaseDataProvider
from src.blockchain import normalizers

class EthereumAdapter(BaseBlockchainAdapter):
    chain = "ethereum"
    network = "mainnet"

    def __init__(self, provider: BaseDataProvider):
        self.provider = provider

    async def get_latest_block_number(self) -> int:
        return await self.provider.fetch_block_number()

    async def get_block_by_number(self, block_number: int) -> BlockData:
        raw_block = await self.provider.fetch_block_by_number(block_number)
        return normalizers.normalize_block(raw_block)

    async def get_transaction_by_hash(self, tx_hash: str) -> TransactionData:
        raw_tx = await self.provider.fetch_transaction_by_hash(tx_hash)
        raw_receipt = await self.provider.fetch_transaction_receipt(tx_hash)
        return normalizers.normalize_transaction(raw_tx, raw_receipt)

    async def get_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[TransactionData]:
        # Not directly supported by raw RPC; will be implemented via Etherscan in future.
        return []

    async def get_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[TransferData]:
        logs = await self.provider.fetch_token_transfers(address, token, start_block, end_block)
        transfers = []
        for log in logs:
            transfers.append(normalizers.normalize_transfer(log))
        return transfers

    async def get_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[SwapEventData]:
        # Not yet implemented.
        return []

    async def get_wallet_balance(self, address: str) -> float:
        balance_wei = await self.provider.fetch_balance(address)
        return balance_wei / 10**18  # convert to ETH

    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        return await self.provider.fetch_token_metadata(token_address)

    async def is_contract(self, address: str) -> bool:
        return await self.provider.is_contract(address)
