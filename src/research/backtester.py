from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from src.research.evaluator import evaluate_signal
from src.research.event_engine import EventEngine

class Backtester:
    def __init__(self, price_data: Dict[str, pd.DataFrame], signals: List[Dict[str, Any]]):
        self.price_data = price_data
        self.signals = signals

    def run(self) -> List[Dict[str, Any]]:
        """Run backtest chronologically and return all evaluation records."""
        # Ensure signals are sorted by timestamp
        engine = EventEngine(self.signals, lambda s: s['timestamp'])
        all_results = []
        for signal in engine:
            results = evaluate_signal(signal, self.price_data)
            all_results.extend(results)
        return all_results
