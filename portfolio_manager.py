"""
مدیریت پورتفولیو برای پوزیشن‌های همزمان.

این ماژول:
    - حداکثر تعداد پوزیشن‌های همزمان را کنترل می‌کند.
    - از باز شدن دو پوزیشن روی یک Symbol جلوگیری می‌کند.
    - بهترین Candidate را برای هر Symbol انتخاب می‌کند.
    - تا سقف ظرفیت باقی‌مانده، برترین Candidateها را برمی‌گرداند.

هیچ سفارشی در این ماژول ارسال نمی‌شود.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

import config
import signal_scoring


class PortfolioManager:
    """
    مدیریت پوزیشن‌های همزمان و انتخاب Candidateهای برتر.

    پارامترها:
        max_positions: حداکثر تعداد پوزیشن‌های همزمان (پیش‌فرض از config).
    """

    def __init__(self, max_positions: Optional[int] = None):
        self.max_positions = max_positions if max_positions is not None else config.MAX_CONCURRENT_POSITIONS
        self.open_positions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # ظرفیت
    # ------------------------------------------------------------------
    def available_slots(self) -> int:
        """تعداد جای خالی برای پوزیشن جدید."""
        return max(0, self.max_positions - len(self.open_positions))

    def is_symbol_open(self, symbol: str) -> bool:
        """بررسی اینکه آیا Symbol در پوزیشن باز وجود دارد."""
        return symbol in self.open_positions

    # ------------------------------------------------------------------
    # مدیریت پوزیشن‌ها
    # ------------------------------------------------------------------
    def add_position(self, symbol: str, position: Dict[str, Any]):
        """افزودن پوزیشن جدید. در صورت تکرار Symbol یا تکمیل ظرفیت خطا می‌دهد."""
        if len(self.open_positions) >= self.max_positions:
            raise RuntimeError("Maximum concurrent positions reached")
        if self.is_symbol_open(symbol):
            raise RuntimeError(f"Position already open for {symbol}")
        self.open_positions[symbol] = position

    def remove_position(self, symbol: str):
        """حذف پوزیشن بسته‌شده."""
        if symbol in self.open_positions:
            del self.open_positions[symbol]

    # ------------------------------------------------------------------
    # انتخاب Candidateها
    # ------------------------------------------------------------------
    def filter_best_per_symbol(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        از بین چند Candidate برای یک Symbol، فقط بالاترین Score را نگه می‌دارد.

        ورودی: لیست Candidateها (ممکن است چند Candidate برای یک Symbol باشد)
        خروجی: لیست یکتا از نظر Symbol با بهترین Score
        """
        best: Dict[str, Dict[str, Any]] = {}
        for cand in candidates:
            sym = cand.get("symbol")
            if sym is None:
                continue
            score = cand.get("score", 0)
            if sym not in best or score > best[sym].get("score", -999):
                best[sym] = cand
        return list(best.values())

    def select_top_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        انتخاب Candidateهای برتر تا سقف ظرفیت باقی‌مانده.

        مراحل:
            1. حذف Candidateهای مربوط به Symbolهایی که پوزیشن باز دارند.
            2. از بین Candidateهای هر Symbol فقط بهترین Score.
            3. رتبه‌بندی با استفاده از signal_scoring.rank_signals (فاز ۱۶).
            4. انتخاب تا سقف available_slots.

        خروجی: لیست Candidateهای انتخاب‌شده برای اجرا.
        """
        if not candidates:
            return []

        # حذف Symbolهای باز
        eligible = [c for c in candidates if not self.is_symbol_open(c.get("symbol", ""))]
        if not eligible:
            return []

        # حذف تکراری‌های هر Symbol
        deduped = self.filter_best_per_symbol(eligible)

        # رتبه‌بندی deterministic
        ranked = signal_scoring.rank_signals(deduped)

        slots = self.available_slots()
        selected = []
        for cand in ranked:
            if len(selected) >= slots:
                break
            selected.append(cand)

        return selected