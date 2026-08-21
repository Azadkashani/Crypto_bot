from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NormalizedSwap(BaseModel):
    chain: str
    dex: str
    protocol_version: Optional[str] = None
    tx_hash: str
    block_number: int
    timestamp: datetime
    log_index: int
    wallet_address: str
    token_in: str
    token_out: str
    amount_in_raw: Optional[str] = None
    amount_out_raw: Optional[str] = None
    amount_in: Optional[float] = None
    amount_out: Optional[float] = None
    token_in_decimals: Optional[int] = None
    token_out_decimals: Optional[int] = None
    token_in_symbol: Optional[str] = None
    token_out_symbol: Optional[str] = None
    side: str  # BUY/SELL/UNKNOWN
    native_value: Optional[float] = None
    usd_value: Optional[float] = None
    pool_address: Optional[str] = None
    router_address: Optional[str] = None
    confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    swap_group_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
