from src.blockchain.normalizers import normalize_block

def test_normalize_block():
    raw = {
        "number": "0x10",
        "hash": "0xabc",
        "timestamp": "0x60",
        "parentHash": "0xdef"
    }
    block = normalize_block(raw)
    assert block.chain == "ethereum"
    assert block.block_number == 16
    assert block.timestamp == 96
