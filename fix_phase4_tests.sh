#!/bin/bash
set -e

echo "🔧 اصلاح تست‌های Phase 4..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# 1. بازنویسی تست WebSocket با mock صحیح
# --------------------------------------------------------------------
cat > tests/unit/ethereum/test_websocket_stream.py <<'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.providers.ethereum.rpc_provider import EthereumRpcProvider

@pytest.mark.asyncio
async def test_stream_blocks_no_ws_url_raises():
    provider = EthereumRpcProvider(ws_url=None)
    with pytest.raises(ValueError):
        await provider.stream_blocks(MagicMock())

@pytest.mark.asyncio
async def test_stream_blocks_with_ws_url_connects_and_calls_callback():
    provider = EthereumRpcProvider(ws_url="ws://dummy")
    callback = AsyncMock()
    # Mock websockets.connect to simulate receiving a new block and then closing
    with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            '{"jsonrpc":"2.0","id":1,"result":"0xsubscription"}',
            '{"jsonrpc":"2.0","method":"eth_subscription","params":{"subscription":"0xsub","result":{"number":"0x10"}}}',
            '{"jsonrpc":"2.0","method":"eth_subscription","params":{"subscription":"0xsub","result":{"number":"0x11"}}}'
        ]
        mock_connect.return_value.__aenter__.return_value = mock_ws
        # Since stream_blocks loops forever, we need to break after some iterations.
        # We'll just set side_effect to raise after a couple to stop.
        # But easier: just test that callback is called by running for a short time.
        # We'll use asyncio.wait_for with timeout.
        import asyncio
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(provider.stream_blocks(callback), timeout=0.5)
        assert callback.called
EOF

# --------------------------------------------------------------------
# 2. بازنویسی تست token metadata cache با mock صحیح
# --------------------------------------------------------------------
cat > tests/unit/ethereum/test_token_metadata_cache.py <<'EOF'
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
EOF

# --------------------------------------------------------------------
# 3. بازنویسی تست historical backfill با mock دیتابیس
# --------------------------------------------------------------------
cat > tests/unit/ethereum/test_historical_backfill.py <<'EOF'
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.collectors.backfill import BackfillEngine
from src.blockchain.ethereum import EthereumAdapter
from src.blockchain.base import BlockData

@pytest.mark.asyncio
async def test_backfill_process_block_mock_db():
    adapter = MagicMock()
    adapter.get_block_by_number = AsyncMock(return_value=BlockData(
        chain="ethereum", network="mainnet", block_number=1, block_hash="0xabc",
        parent_hash="0xdef", timestamp=123
    ))
    # Mock the SessionLocal and repository to avoid real DB
    with patch('src.collectors.backfill.SessionLocal') as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        # Mock repository methods to do nothing
        with patch('src.collectors.backfill.BlockRepository') as mock_block_repo_cls:
            mock_block_repo = MagicMock()
            mock_block_repo.get_by_number = MagicMock(return_value=None)
            mock_block_repo_cls.return_value = mock_block_repo
            engine = BackfillEngine(adapter)
            await engine.process_block(1)
            # Assert that block was added
            assert mock_block_repo.add.called
            mock_session.commit.assert_called()
EOF

# --------------------------------------------------------------------
# 4. اجرای تست‌ها
# --------------------------------------------------------------------
echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

# --------------------------------------------------------------------
# 5. Commit و Push اصلاحات
# --------------------------------------------------------------------
echo "📦 Commit و Push اصلاحات تست‌ها..."
git add -A
git commit -m "fix: make Phase 4 tests non-hanging and mock DB properly"
git push origin main

echo "🎉 اصلاحات اعمال شد و به گیت‌هاب Push شد."
