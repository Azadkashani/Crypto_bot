import pytest
from unittest.mock import AsyncMock, MagicMock
from src.providers.ethereum.etherscan import EtherscanProvider

@pytest.mark.asyncio
async def test_fetch_token_transfers():
    provider = EtherscanProvider(api_key="dummy", base_url="http://dummy")
    provider._client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"status": "1", "result": [{"hash": "0x1", "tokenSymbol": "USDC"}]}
    provider._client.get = AsyncMock(return_value=mock_response)
    result = await provider.fetch_token_transfers("0xaddr", "0xtoken", 100, 200)
    assert len(result) == 1
    assert result[0]["tokenSymbol"] == "USDC"
