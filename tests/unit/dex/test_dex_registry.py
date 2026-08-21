import pytest
from src.dex.registry import DEXRegistry
from src.dex.ethereum.uniswap import UniswapV2Adapter

def test_registry_detect_uniswap():
    registry = DEXRegistry()
    adapter = UniswapV2Adapter()
    registry.register("uniswap_v2", adapter)
    log = {"topics": [adapter.swap_topic, "0xsender", "0xrecipient"], "address": "0xpool", "data": "0x" + "0"*256}
    detected = registry.detect(log)
    assert detected is adapter
