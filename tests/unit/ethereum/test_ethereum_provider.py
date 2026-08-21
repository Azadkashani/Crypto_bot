import pytest
from unittest.mock import AsyncMock, MagicMock
from src.providers.ethereum.rpc_provider import EthereumRpcProvider

@pytest.mark.asyncio
async def test_fetch_block_number():
    provider = EthereumRpcProvider("http://dummy")
    provider._client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"result": "0x10", "error": None}
    provider._client.post = AsyncMock(return_value=mock_response)
    result = await provider.fetch_block_number()
    assert result == 16
