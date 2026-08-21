import pytest
from unittest.mock import MagicMock
from src.providers.ethereum.rpc_provider import EthereumRpcProvider

def test_stream_blocks_not_implemented():
    provider = EthereumRpcProvider(ws_url="ws://dummy")
    with pytest.raises(NotImplementedError):
        # Since stream_blocks is async, we need to run it via asyncio
        import asyncio
        asyncio.run(provider.stream_blocks(MagicMock()))

def test_stream_logs_not_implemented():
    provider = EthereumRpcProvider(ws_url="ws://dummy")
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(provider.stream_logs([], MagicMock()))
