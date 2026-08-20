from abc import ABC, abstractmethod

class BaseMarketDataProvider(ABC):
    @abstractmethod
    def get_price(self, token: str, timestamp: int) -> float:
        ...
    @abstractmethod
    def get_volume_24h(self, token: str) -> float:
        ...
    @abstractmethod
    def get_ohlcv(self, token: str, interval: str) -> list:
        ...
