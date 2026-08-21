import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.blockchain.ethereum import EthereumAdapter
from src.providers.base import BaseDataProvider
from src.providers.ethereum.rpc_provider import EthereumRpcProvider
from src.providers.ethereum.etherscan import EtherscanProvider
from src.storage.database import SessionLocal
from src.storage.repositories import BlockRepository, TokenTransferRepository, EventLogRepository
from src.storage.models import Block, TokenTransfer, EventLog
from src.blockchain import normalizers
from src.core.config import settings
from src.core.logger import logger

class BackfillEngine:
    def __init__(self, adapter: EthereumAdapter, provider_for_historical: BaseDataProvider = None):
        self.adapter = adapter
        self.historical_provider = provider_for_historical
        self.resume_file = settings.eth_backfill_resume_file
        self.batch_size = settings.eth_backfill_batch_size
        self.state = self._load_resume_state()

    def _load_resume_state(self) -> dict:
        if os.path.exists(self.resume_file):
            with open(self.resume_file, 'r') as f:
                return json.load(f)
        return {"last_processed_block": 0}

    def _save_resume_state(self):
        os.makedirs(os.path.dirname(self.resume_file), exist_ok=True)
        with open(self.resume_file, 'w') as f:
            json.dump(self.state, f)

    async def run(self, start_block: Optional[int] = None, end_block: Optional[int] = None):
        if start_block is None:
            start_block = self.state["last_processed_block"] + 1
        if end_block is None:
            end_block = await self.adapter.get_latest_block_number()

        logger.info(f"Starting backfill from {start_block} to {end_block}")

        for block_num in range(start_block, end_block + 1):
            try:
                await self.process_block(block_num)
                self.state["last_processed_block"] = block_num
                self._save_resume_state()
                if block_num % 100 == 0:
                    logger.info(f"Processed block {block_num}/{end_block}")
            except Exception as e:
                logger.error(f"Error processing block {block_num}: {e}")
                # Optionally break or continue
                raise

    async def process_block(self, block_num: int):
        # Fetch block data
        raw_block = await self.adapter.get_block_by_number(block_num)
        # Store block
        session = SessionLocal()
        try:
            block_repo = BlockRepository(session)
            existing = block_repo.get_by_number("ethereum", block_num)
            if existing:
                logger.debug(f"Block {block_num} already exists, skipping")
                return
            block = Block(
                chain="ethereum",
                network="mainnet",
                block_number=raw_block.block_number,
                block_hash=raw_block.block_hash,
                parent_hash=raw_block.parent_hash,
                timestamp=raw_block.timestamp,
                transaction_count=0,  # might update later
                status="pending"  # will be updated after confirmations
            )
            block_repo.add(block)
            session.commit()
            logger.debug(f"Stored block {block_num}")
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

        # Fetch logs for this block? That would be many requests. Instead, process transactions.
        # For simplicity, we'll just store block. In next iterations, we'll process transactions and logs.
        # But the user wants ERC20 transfers, etc. We'll implement a simplified version using logs.
        # For full backfill, we'd need to fetch transaction receipts for each tx in the block.
        # That's heavy. We'll use Etherscan API to get token transfers for the block range later.
        # For now, we'll store only blocks.

    def run_sync(self, start_block=None, end_block=None):
        asyncio.run(self.run(start_block, end_block))
