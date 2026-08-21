import pytest
from unittest.mock import AsyncMock, MagicMock
from src.providers.ethereum.rpc_provider import EthereumRpcProvider

@pytest.mark.asyncio
async def test_token_metadata_cached():
    provider = EthereumRpcProvider(rpc_url="http://dummy")
    # Mock _rpc_call to return proper hex values for symbol, name, decimals
    async def mock_rpc_call(method, params):
        if method == "eth_call":
            # For symbol, return '0x555344430000...' (USDC)
            if params[0]["data"] == "0x95d89b41":
                return "0x5553444300000000000000000000000000000000000000000000000000000000"
            # For name, return '0x55534420436f696e000000...' (USD Coin)
            if params[0]["data"] == "0x06fdde03":
                return "0x55534420436f696e0000000000000000000000000000000000000000000000"
            # For decimals, return 0x6
            if params[0]["data"] == "0x313ce567":
                return "0x6"
        return "0x"
    provider._rpc_call = AsyncMock(side_effect=mock_rpc_call)
    metadata = await provider.fetch_token_metadata("0xtoken")
    assert metadata["symbol"] == "USDC"
    assert metadata["name"] == "USD Coin"
    assert metadata["decimals"] == 6
