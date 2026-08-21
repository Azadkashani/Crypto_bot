from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_no_lookahead():
    t1 = datetime(2024,1,1,tzinfo=UTC)
    t2 = datetime(2024,1,2,tzinfo=UTC)
    swap1 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                           timestamp=t1, log_index=0, wallet_address="0xw",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95)
    swap2 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                           timestamp=t2, log_index=0, wallet_address="0xw",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=999000, confidence=95)
    agg_t1 = WalletAggregator([swap1, swap2], as_of=t1)
    stats_t1 = agg_t1.aggregate()["0xw"]
    assert stats_t1['total_volume_usd'] == 1000
