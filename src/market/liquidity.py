from abc import ABC, abstractmethod

class BaseLiquidityProvider(ABC):
    @abstractmethod
    def get_liquidity(self, token: str, chain: str) -> float:
        ...
