from typing import Dict, Set

class ExcludedAddressRegistry:
    def __init__(self):
        self._excluded: Dict[str, Set[str]] = {}
        self._load_defaults()

    def _load_defaults(self):
        self.add_address("0x0000000000000000000000000000000000000000", "burn", "burn", "official")

    def add_address(self, address: str, category: str, reason: str, source: str):
        addr = address.lower()
        if category not in self._excluded:
            self._excluded[category] = set()
        self._excluded[category].add(addr)

    def is_excluded(self, address: str) -> bool:
        addr = address.lower()
        for addrs in self._excluded.values():
            if addr in addrs:
                return True
        return False

    def get_category(self, address: str) -> str:
        addr = address.lower()
        for category, addrs in self._excluded.items():
            if addr in addrs:
                return category
        return None
