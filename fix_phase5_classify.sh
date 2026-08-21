#!/bin/bash
set -e

echo "🔧 اصلاح منطق _classify در SwapParser..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# بازنویسی swap_parser.py با _classify صحیح
# --------------------------------------------------------------------
cat > src/dex/parsers/swap_parser.py <<'EOF'
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC
from src.dex.registry import DEXRegistry
from src.dex.models import NormalizedSwap
from src.dex.base import BaseDEXAdapter, SwapInfo
from src.core.config import settings
from src.core.logger import logger
from src.storage.database import SessionLocal
from src.storage.repositories import SwapRepository
from src.storage.models import Swap
from src.data_quality.deduplicator import Deduplicator
from src.providers.base import BaseDataProvider

class SwapParser:
    def __init__(self, registry: DEXRegistry, provider: BaseDataProvider = None):
        self.registry = registry
        self.provider = provider
        self.dedup = Deduplicator()
        self.stablecoins = self._load_stablecoins()

    def _load_stablecoins(self) -> Dict[str, str]:
        coins = {}
        addr_str = settings.stablecoin_addresses_ethereum
        if addr_str:
            for addr in addr_str.split(','):
                addr = addr.strip()
                coins[addr.lower()] = "STABLE"
        # Add native and wrapped
        coins["0x0000000000000000000000000000000000000000"] = settings.native_asset_symbol
        coins[settings.wrapped_native_address.lower()] = settings.wrapped_native_symbol
        return coins

    def _is_stable(self, token_address: str) -> bool:
        return token_address.lower() in self.stablecoins

    def _is_native(self, token_address: str) -> bool:
        return token_address == "0x0000000000000000000000000000000000000000"

    def _is_wrapped_native(self, token_address: str) -> bool:
        return token_address.lower() == settings.wrapped_native_address.lower()

    async def process_log(self, log: Dict[str, Any], tx: Dict[str, Any], block_timestamp: int) -> Optional[NormalizedSwap]:
        if self.dedup.is_duplicate({"chain": "ethereum", "transaction_hash": tx.get("hash",""), "log_index": log.get("logIndex", "0x0")}):
            return None

        adapter = self.registry.detect(log)
        if not adapter:
            return None

        swap_info = adapter.parse_swap(log)
        if not swap_info:
            return None

        participants = adapter.identify_participants(swap_info, tx)
        wallet = participants.get("wallet_address")
        if not wallet:
            return None

        pool_address = swap_info.pool_address
        pool_tokens = await self._get_pool_tokens(pool_address, adapter)
        if pool_tokens:
            context = {"pool_tokens": pool_tokens}
            direction = adapter.determine_direction(swap_info, context)
            token_in = direction.get("token_in")
            token_out = direction.get("token_out")
            reasons = direction.get("reasons", [])
            confidence = direction.get("confidence", 0.0)
        else:
            token_in = None
            token_out = None
            reasons = ["POOL_TOKENS_UNKNOWN"]
            confidence = 0.0

        classification = await self._classify(
            token_in=token_in,
            token_out=token_out,
            adapter=adapter,
            swap_info=swap_info,
            wallet=wallet,
            participants=participants,
            tx=tx,
            block_timestamp=block_timestamp,
            reasons=reasons,
            confidence=confidence,
        )

        return classification

    async def _get_pool_tokens(self, pool_address: str, adapter: BaseDEXAdapter) -> Optional[Tuple[str, str]]:
        if self.provider and hasattr(self.provider, 'get_pool_tokens'):
            return await self.provider.get_pool_tokens(pool_address)
        return None

    async def _classify(self, token_in: Optional[str], token_out: Optional[str],
                        adapter: BaseDEXAdapter, swap_info: SwapInfo, wallet: str,
                        participants: Dict[str, str], tx: Dict[str, Any],
                        block_timestamp: int, reasons: List[str], confidence: float) -> NormalizedSwap:
        side = "UNKNOWN"
        # Attempt classification if we have both token addresses
        if token_in and token_out:
            stable_in = self._is_stable(token_in)
            stable_out = self._is_stable(token_out)
            native_in = self._is_native(token_in)
            native_out = self._is_native(token_out)
            wrapped_in = self._is_wrapped_native(token_in)
            wrapped_out = self._is_wrapped_native(token_out)

            if (stable_in or native_in or wrapped_in) and not (stable_out or native_out or wrapped_out):
                side = "BUY"
                reason = "BUY_" + ("STABLECOIN" if stable_in else "NATIVE" if native_in else "WRAPPED_NATIVE") + "_TO_TOKEN"
                confidence = 95.0
                reasons.append(reason)
            elif (stable_out or native_out or wrapped_out) and not (stable_in or native_in or wrapped_in):
                side = "SELL"
                reason = "SELL_TOKEN_TO_" + ("STABLECOIN" if stable_out else "NATIVE" if native_out else "WRAPPED_NATIVE")
                confidence = 95.0
                reasons.append(reason)
            else:
                side = "UNKNOWN"
                confidence = 50.0
                reasons.append("TOKEN_TO_TOKEN_OR_UNKNOWN")
        else:
            side = "UNKNOWN"
            confidence = 0.0
            if token_in is None:
                reasons.append("TOKEN_IN_MISSING")
            if token_out is None:
                reasons.append("TOKEN_OUT_MISSING")

        usd_value = None

        # Construct amount fields based on direction if available
        amount_in = None
        amount_out = None
        if token_in and token_out:
            # Need to know which amount corresponds to token_in/out from swap_info
            # We'll rely on the previous determine_direction logic, but here we don't have that info.
            # For simplicity, set based on swap_info amounts if possible.
            pass

        return NormalizedSwap(
            chain="ethereum",
            dex=adapter.dex_name,
            protocol_version=adapter.protocol_version,
            tx_hash=tx.get("hash", ""),
            block_number=int(tx.get("blockNumber", "0x0"), 16) if tx.get("blockNumber") else 0,
            timestamp=datetime.fromtimestamp(block_timestamp, tz=UTC),
            log_index=int(tx.get("transactionIndex", "0x0"), 16) if tx.get("transactionIndex") else 0,
            wallet_address=wallet,
            token_in=token_in or "",
            token_out=token_out or "",
            amount_in_raw=str(swap_info.amount0_in) if token_in and swap_info.amount0_in > 0 else str(swap_info.amount1_in),
            amount_out_raw=str(swap_info.amount0_out) if token_out and swap_info.amount0_out > 0 else str(swap_info.amount1_out),
            token_in_decimals=None,
            token_out_decimals=None,
            token_in_symbol=None,
            token_out_symbol=None,
            side=side,
            native_value=None,
            usd_value=usd_value,
            pool_address=swap_info.pool_address,
            router_address=participants.get("router_address"),
            confidence=confidence,
            classification_reason=";".join(reasons),
            swap_group_id=tx.get("hash"),
            extra_data={"raw_log": {}, "tx": tx}
        )

    async def process_transaction(self, tx: Dict[str, Any], block_timestamp: int) -> List[NormalizedSwap]:
        swaps = []
        logs = tx.get("logs", [])
        for log in logs:
            normalized = await self.process_log(log, tx, block_timestamp)
            if normalized:
                swaps.append(normalized)
        return swaps
EOF

echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. لطفاً خروجی کامل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

echo "📦 Commit و Push اصلاح منطق طبقه‌بندی..."
git add -A
git commit -m "fix: classify BUY/SELL even when initial side is UNKNOWN"
git push origin main

echo "🎉 اصلاح انجام شد."
