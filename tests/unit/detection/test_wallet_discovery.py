from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_discovery():
    swaps = [
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                       timestamp=datetime(2024,1,1,tzinfo=UTC), log_index=0, wallet_address="0xw1",
                       token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95),
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                       timestamp=datetime(2024,1,2,tzinfo=UTC), log_index=0, wallet_address="0xw2",
                       token_in="0xtoken", token_out="0xusdc", side="SELL", usd_value=800, confidence=95),
    ]
    agg = WalletAggregator(swaps)
    stats = agg.aggregate()
    assert len(stats) == 2
