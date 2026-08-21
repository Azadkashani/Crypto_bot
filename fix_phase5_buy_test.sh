#!/bin/bash
set -e

echo "🔧 اصلاح تست Buy Classification..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# بازنویسی تست test_buy_classification.py با اضافه کردن Stablecoin دستی
# --------------------------------------------------------------------
cat > tests/unit/dex/test_buy_classification.py <<'EOF'
import pytest
from src.dex.ethereum.uniswap import UniswapV2Adapter
from src.dex.base import SwapInfo
from src.dex.parsers.swap_parser import SwapParser
from src.dex.registry import DEXRegistry

@pytest.mark.asyncio
async def test_stable_to_token_buy():
    adapter = UniswapV2Adapter()
    swap = SwapInfo(
        dex="uniswap_v2", protocol_version="v2",
        pool_address="0xpool", sender="0xrouter", recipient="0xwallet",
        amount0_in=1000, amount1_in=0, amount0_out=0, amount1_out=500
    )
    pool_tokens = ("0xstable", "0xtoken")
    reg = DEXRegistry()
    reg.register("uniswap_v2", adapter)
    parser = SwapParser(registry=reg, provider=None)
    # اضافه کردن استیبل کوین ساختگی به لیست برای تست
    parser.stablecoins["0xstable"] = "STABLE"
    parser.stablecoins["0xtoken"] = "TOKEN"  # فقط برای اطمینان

    tx = {
        "hash": "0xtx",
        "from": "0xwallet",
        "blockNumber": "0x1",
        "transactionIndex": "0x0",
        "logs": []
    }
    # فراخوانی _classify با side=UNKNOWN و token_in/out مشخص
    classified = await parser._classify(
        "UNKNOWN", pool_tokens[0], pool_tokens[1],
        adapter, swap, "0xwallet", {"router_address": "0xrouter"},
        tx, 0, [], 0
    )
    assert classified.side == "BUY"
    assert classified.confidence >= 90
    assert "STABLECOIN" in classified.classification_reason
EOF

echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

echo "📦 Commit و Push اصلاح تست..."
git add -A
git commit -m "fix: adjust buy classification test to mock stablecoin"
git push origin main

echo "🎉 اصلاح انجام شد."
