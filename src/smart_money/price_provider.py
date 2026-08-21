from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional

class PriceProvider(ABC):
    @abstractmethod
    def get_price(self, token: str, timestamp: int) -> Optional[float]:
        """Return price at or before timestamp."""
        ...

class MockPriceProvider(PriceProvider):
    """Mock provider that reads from a dict of token -> list of (timestamp, price)."""
    def __init__(self, price_data: Dict[str, List[Tuple[int, float]]]):
        self.price_data = price_data

    def get_price(self, token: str, timestamp: int) -> Optional[float]:
        if token not in self.price_data:
            return None
        series = self.price_data[token]
        # Find the latest price at or before timestamp
        best = None
        for ts, price in series:
            if ts <= timestamp:
                best = price
            else:
                break
        return best
