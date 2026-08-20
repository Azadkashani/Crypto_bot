from abc import ABC, abstractmethod
from typing import List
from src.core.constants import ClassificationLabel
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    label: ClassificationLabel
    confidence: float
    reasons: List[str] = []

class BaseTransactionClassifier(ABC):
    @abstractmethod
    def classify(self, transaction: dict, context: dict) -> ClassificationResult:
        ...
