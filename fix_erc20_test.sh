#!/bin/bash
set -e

echo "🔧 اصلاح تست ERC20 با آدرس‌های کامل..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# بازنویسی تست ERC20 با آدرس‌های معتبر و Topicهای استاندارد
# --------------------------------------------------------------------
cat > tests/unit/ethereum/test_erc20_transfer.py <<'EOF'
from src.blockchain.normalizers import normalize_transfer

def test_normalize_transfer():
    # Use full 32-byte topics with address in last 20 bytes (40 hex)
    from_addr = "0x" + "0"*24 + "abcdeabcdeabcdeabcdeabcdeabcdeabcdeabc"
    to_addr = "0x" + "0"*24 + "fabcdeabcdeabcdeabcdeabcdeabcdeabcdeabc"
    log = {
        "blockNumber": "0x1",
        "transactionHash": "0xtx",
        "logIndex": "0x0",
        "address": "0xtoken",
        "topics": ["0xTransfer", from_addr, to_addr],
        "data": "0x0000000000000000000000000000000000000000000000000000000000000064",
        "blockHash": "0xblock"
    }
    transfer = normalize_transfer(log)
    assert transfer.token_address == "0xtoken"
    assert transfer.from_address == "0xabcdeabcdeabcdeabcdeabcdeabcdeabcdeabc"
    assert transfer.to_address == "0xfabcdeabcdeabcdeabcdeabcdeabcdeabcdeabc"
    assert transfer.amount == 100
EOF

# --------------------------------------------------------------------
# اجرای تست‌ها
# --------------------------------------------------------------------
echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

# --------------------------------------------------------------------
# Commit و Push
# --------------------------------------------------------------------
echo "📦 Commit و Push اصلاح تست ERC20..."
git add -A
git commit -m "fix: correct ERC20 test with full-length addresses and topics"
git push origin main

echo "🎉 اصلاح تست انجام شد و به گیت‌هاب Push شد."
