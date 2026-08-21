#!/bin/bash
set -e

echo "🔧 اصلاح نهایی تست ERC20 با آدرس معتبر..."

cd ~/Crypto_bot

cat > tests/unit/ethereum/test_erc20_transfer.py <<'EOF'
from src.blockchain.normalizers import normalize_transfer

def test_normalize_transfer():
    # Use a valid 32-byte topic: 24 zeros + 40 hex address
    # Address: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 (mixed case)
    from_topic = "0x" + "0"*24 + "d8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    to_topic   = "0x" + "0"*24 + "1f9090aaE28b8a3dCeaDf281B0F12828e676c326"
    log = {
        "blockNumber": "0x1",
        "transactionHash": "0xtx",
        "logIndex": "0x0",
        "address": "0xtoken",
        "topics": ["0xTransfer", from_topic, to_topic],
        "data": "0x0000000000000000000000000000000000000000000000000000000000000064",
        "blockHash": "0xblock"
    }
    transfer = normalize_transfer(log)
    assert transfer.token_address == "0xtoken"
    # Expected lowercase addresses extracted from last 20 bytes
    assert transfer.from_address == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    assert transfer.to_address   == "0x1f9090aae28b8a3dceadf281b0f12828e676c326"
    assert transfer.amount == 100
EOF

echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

echo "📦 Commit و Push اصلاح تست ERC20..."
git add -A
git commit -m "fix: correct ERC20 transfer test with valid 32-byte topics"
git push origin main

echo "🎉 Phase 4 کامل شد."
