import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.market.gate_data import GatePublicData

@pytest.mark.asyncio
async def test_get_candlesticks():
    provider = GatePublicData()
    provider._client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"t": 1609459200, "o": "100", "h": "110", "l": "95", "c": "105", "v": "1000"}
    ]
    provider._client.get = AsyncMock(return_value=mock_response)

    result = await provider.get_futures_candlesticks("BTC_USDT", "5m", 10)
    assert len(result) == 1
    assert result[0]["c"] == "105"
    # Verify URL and params
    provider._client.get.assert_called_once()
    args, kwargs = provider._client.get.call_args
    assert args[0].endswith("/futures/usdt/candlesticks")
    assert kwargs["params"]["contract"] == "BTC_USDT"
