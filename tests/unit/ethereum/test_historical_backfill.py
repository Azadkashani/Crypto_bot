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
