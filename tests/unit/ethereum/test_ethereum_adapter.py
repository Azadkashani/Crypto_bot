import pytest
from unittest.mock import AsyncMock, MagicMock
from src.blockchain.ethereum import EthereumAdapter
from src.blockchain.base import BlockData

@pytest.mark.asyncio
async def test_get_latest_block_number():
    mock_provider = MagicMock()
    mock_provider.fetch_block_number = AsyncMock(return_value=12345)
    adapter = EthereumAdapter(mock_provider)
    result = await adapter.get_latest_block_number()
    assert result == 12345

@pytest.mark.asyncio
async def test_get_block_by_number():
    mock_provider = MagicMock()
    raw_block = {
        "number": "0x10",
        "hash": "0xabc",
        "timestamp": "0x60",
        "parentHash": "0xdef"
    }
    mock_provider.fetch_block_by_number = AsyncMock(return_value=raw_block)
    adapter = EthereumAdapter(mock_provider)
    block = await adapter.get_block_by_number(16)
    assert isinstance(block, BlockData)
    assert block.block_number == 16
    assert block.block_hash == "0xabc"
