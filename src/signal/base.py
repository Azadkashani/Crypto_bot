from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any

class SignalData(BaseModel):
    token: str
    chain: str
    timestamp: int
    signal_score: float
    confidence: float
    components: Dict[str, Any]
    regime: str
    gate_available: bool
    mode: str

class BaseSignalGenerator(ABC):
    @abstractmethod
    def generate(self, context: Dict[str, Any]) -> SignalData:
        ...
