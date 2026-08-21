from src.detection.excluded_addresses import ExcludedAddressRegistry
def test_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xabc", "CEX", "Binance", "official")
    assert reg.is_excluded("0xabc")
