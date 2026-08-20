from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any

class ScoreResult(BaseModel):
    score: float
    features: Dict[str, float]
    explanation: Dict[str, Any]

class BaseScorer(ABC):
    @abstractmethod
    def calculate(self, wallet_data: Dict[str, Any]) -> ScoreResult:
        ...
