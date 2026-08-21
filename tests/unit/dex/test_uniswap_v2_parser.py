import pytest
from src.dex.ethereum.uniswap import UniswapV2Adapter
from src.dex.base import SwapInfo

def test_parse_swap():
    adapter = UniswapV2Adapter()
    # ساخت data به صورت تمیز بدون مشکل ادامه خط
    # ترتیب: amount0In, amount1In, amount0Out, amount1Out
    data = "0x" + \
        format(100, '064x') + \
        format(0, '064x') + \
        format(0, '064x') + \
        format(200, '064x')

    log = {
        "topics": [adapter.swap_topic, "0x" + "0"*24 + "abc", "0x" + "0"*24 + "def"],
        "address": "0xpool",
        "data": data
    }
    swap = adapter.parse_swap(log)
    assert swap is not None
    assert swap.amount0_in == 100
    assert swap.amount1_in == 0
    assert swap.amount0_out == 0
    assert swap.amount1_out == 200
