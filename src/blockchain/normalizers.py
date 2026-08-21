from datetime import datetime, UTC
from typing import Dict, Any
from src.blockchain.base import BlockData, TransactionData, TransferData, SwapEventData
from src.core.constants import Chain

def normalize_block(block: Dict[str, Any]) -> BlockData:
    return BlockData(
        chain=Chain.ETHEREUM,
        network="mainnet",
        block_number=int(block["number"], 16),
        block_hash=block["hash"],
        timestamp=int(block["timestamp"], 16),
        parent_hash=block["parentHash"],
        extra_data={"raw": block}
    )

def normalize_transaction(tx: Dict[str, Any], receipt: Dict[str, Any]) -> TransactionData:
    return TransactionData(
        chain=Chain.ETHEREUM,
        network="mainnet",
        block_number=int(tx["blockNumber"], 16) if tx.get("blockNumber") else 0,
        block_hash=tx.get("blockHash", ""),
        transaction_hash=tx["hash"],
        transaction_index=int(tx["transactionIndex"], 16) if tx.get("transactionIndex") else 0,
        from_address=tx["from"],
        to_address=tx.get("to"),
        value=int(tx["value"], 16) if tx.get("value") else 0,
        timestamp=0,  # Will be filled from block
        status="confirmed" if receipt.get("status") == "0x1" else "failed",
        gas_used=int(receipt["gasUsed"], 16) if receipt.get("gasUsed") else None,
        gas_price=int(tx["gasPrice"], 16) if tx.get("gasPrice") else None,
        logs=receipt.get("logs", []),
        extra_data={"raw_tx": tx, "raw_receipt": receipt}
    )

def normalize_transfer(log: Dict[str, Any]) -> TransferData:
    # ERC20 Transfer event: topics[0] = Transfer, topics[1] = from, topics[2] = to, data = amount
    return TransferData(
        chain=Chain.ETHEREUM,
        network="mainnet",
        block_number=int(log["blockNumber"], 16),
        transaction_hash=log["transactionHash"],
        log_index=int(log["logIndex"], 16),
        token_address=log["address"],
        from_address="0x" + log["topics"][1][-40:],
        to_address="0x" + log["topics"][2][-40:],
        amount=int(log["data"], 16),
        token_decimals=0,  # unknown, can be fetched later
        token_symbol=None,
        timestamp=0,
        extra_data={"raw": log}
    )

def normalize_swap_event(log: Dict[str, Any]) -> SwapEventData:
    # Placeholder: will be implemented with DEX adapters later.
    raise NotImplementedError("Swap normalization not yet implemented.")
