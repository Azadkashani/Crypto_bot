from typing import Dict, Any, Optional
from src.dex.base import BaseDEXAdapter, SwapInfo
from src.core.config import settings

class UniswapV2Adapter(BaseDEXAdapter):
    dex_name = "uniswap_v2"
    chain = "ethereum"
    protocol_version = "v2"
    swap_topic = settings.dex_swap_topic_uniswap_v2

    def identify_swap(self, log: Dict[str, Any]) -> bool:
        if log.get("topics") and log["topics"][0] == self.swap_topic:
            return True
        return False

    def parse_swap(self, log: Dict[str, Any]) -> Optional[SwapInfo]:
        # Uniswap V2 Swap event:
        # topics: [topic0, sender, to]
        # data: amount0In, amount1In, amount0Out, amount1Out (uint256 each)
        try:
            topics = log.get("topics", [])
            if len(topics) < 3:
                return None
            sender = "0x" + topics[1][-40:]
            recipient = "0x" + topics[2][-40:]
            data = log.get("data", "0x")
            # Remove 0x prefix
            data = data[2:]
            # Each uint256 is 64 hex chars
            amount0_in = int(data[0:64], 16)
            amount1_in = int(data[64:128], 16)
            amount0_out = int(data[128:192], 16)
            amount1_out = int(data[192:256], 16)
            return SwapInfo(
                dex=self.dex_name,
                protocol_version=self.protocol_version,
                pool_address=log.get("address", ""),
                sender=sender,
                recipient=recipient,
                amount0_in=amount0_in,
                amount1_in=amount1_in,
                amount0_out=amount0_out,
                amount1_out=amount1_out,
            )
        except Exception:
            return None

    def identify_participants(self, swap: SwapInfo, tx: Dict[str, Any]) -> Dict[str, str]:
        # The trader is usually tx['from'] or swap.recipient, but we can't be sure.
        # For now, choose the swap.recipient if it's not pool, else tx['from'].
        # We'll refine later with more context.
        pool = swap.pool_address
        recipient = swap.recipient
        sender = swap.sender
        tx_from = tx.get("from", "")
        # Basic heuristic: if recipient is not pool, use recipient; else use tx_from.
        wallet = recipient if recipient.lower() != pool.lower() else tx_from
        return {
            "wallet_address": wallet,
            "router_address": sender,  # sender is often router
            "pool_address": pool,
            "tx_from": tx_from,
        }

    def determine_direction(self, swap: SwapInfo, context: Dict[str, Any]) -> Dict[str, Any]:
        # Determine token_in and token_out based on amounts.
        # We need token addresses for token0 and token1. We can get from context['pool_tokens'] (if provided)
        # Otherwise, we can't determine direction confidently -> UNKNOWN.
        pool_tokens = context.get("pool_tokens")
        if not pool_tokens:
            return {
                "side": "UNKNOWN",
                "token_in": None,
                "token_out": None,
                "reasons": ["POOL_TOKENS_UNKNOWN"],
                "confidence": 0.0,
            }

        token0, token1 = pool_tokens  # tuple
        amount0_in = swap.amount0_in
        amount1_in = swap.amount1_in
        amount0_out = swap.amount0_out
        amount1_out = swap.amount1_out

        # Determine direction:
        # If amount0_in > 0 and amount1_out > 0: token0 -> token1
        # If amount1_in > 0 and amount0_out > 0: token1 -> token0
        # (Usually one of amount0_in or amount1_in is zero in V2 swaps)
        if amount0_in > 0 and amount1_out > 0:
            token_in = token0
            token_out = token1
            amount_in = amount0_in
            amount_out = amount1_out
        elif amount1_in > 0 and amount0_out > 0:
            token_in = token1
            token_out = token0
            amount_in = amount1_in
            amount_out = amount0_out
        else:
            # Multi-hop or complex
            return {
                "side": "UNKNOWN",
                "token_in": None,
                "token_out": None,
                "reasons": ["AMBIGUOUS_DIRECTION"],
                "confidence": 0.0,
            }

        # Determine buy/sell based on stablecoin/native knowledge
        # This logic will be in a separate classifier, not here.
        return {
            "side": "UNKNOWN",
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": amount_in,
            "amount_out": amount_out,
            "reasons": [],
            "confidence": 50.0,  # base confidence before classifier
        }
