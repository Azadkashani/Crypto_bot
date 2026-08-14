"""
مدیریت پورتفولیو برای پوزیشن‌های همزمان.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import config
import signal_scoring


class PortfolioManager:
    """
    مدیریت حداکثر MAX_CONCURRENT_POSITIONS و فیلتر Symbolهای باز.
    """

    def __init__(self, max_positions: Optional[int] = None):
        self.max_positions = max_positions or config.MAX_CONCURRENT_POSITIONS
        self.open_positions: Dict[str, Dict[str, Any]] = {}

    def available_slots(self) -> int:
        return max(0, self.max_positions - len(self.open_positions))

    def is_symbol_open(self, symbol: str) -> bool:
        return symbol in self.open_positions

    def add_position(self, symbol: str, position: Dict[str, Any]):
        if len(self.open_positions) >= self.max_positions:
            raise RuntimeError("Maximum concurrent positions reached")
        if self.is_symbol_open(symbol):
            raise RuntimeError(f"Position already open for {symbol}")
        self.open_positions[symbol] = position

    def remove_position(self, symbol: str):
        if symbol in self.open_positions:
            del self.open_positions[symbol]

    def filter_best_per_symbol(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        از بین چند Candidate یک Symbol، فقط بالاترین Score را نگه می‌دارد.
        """
        best: Dict[str, Dict[str, Any]] = {}
        for cand in candidates:
            sym = cand.get("symbol")
            score = cand.get("score", 0)
            if sym not in best or score > best[sym].get("score", -999):
                best[sym] = cand
        return list(best.values())

    def select_top_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        انتخاب Candidateهای برتر تا سقف ظرفیت باقی‌مانده.
        """
        if not candidates:
            return []

        # حذف Candidateهای مربوط به Symbolهای باز
        eligible = [c for c in candidates if not self.is_symbol_open(c["symbol"])]
        if not eligible:
            return []

        # فقط بهترین Candidate برای هر Symbol
        deduped = self.filter_best_per_symbol(eligible)

        # رتبه‌بندی با منطق فاز ۱۶
        ranked = signal_scoring.rank_signals(deduped)

        selected = []
        slots = self.available_slots()
        for cand in ranked:
            if len(selected) >= slots:
                break
            selected.append(cand)

        return selected
