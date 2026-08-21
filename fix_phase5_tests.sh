#!/bin/bash
set -e

echo "🔧 اصلاح خطای نحوی در تست Uniswap V2..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# بازنویسی فایل تست با ساختار صحیح
# --------------------------------------------------------------------
cat > tests/unit/dex/test_uniswap_v2_parser.py <<'EOF'
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
EOF

echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

echo "📦 Commit و Push اصلاح تست..."
git add -A
git commit -m "fix: correct syntax error in uniswap v2 parser test"
git push origin main

echo "🎉 اصلاح انجام شد."
