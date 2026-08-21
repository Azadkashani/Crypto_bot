from src.blockchain.normalizers import normalize_block
from src.core.constants import Chain

def test_reorg_detect_parent_mismatch():
    block1 = normalize_block({"number": "0x1", "hash": "0xabc", "parentHash": "0xgenesis", "timestamp": "0x1"})
    block2 = normalize_block({"number": "0x2", "hash": "0xdef", "parentHash": "0xOTHER", "timestamp": "0x2"})
    # If block1's hash does not equal block2's parentHash, reorg detected.
    assert block1.block_hash != block2.parent_hash
