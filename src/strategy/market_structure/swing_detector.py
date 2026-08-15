# FILE: src/strategy/market_structure/swing_detector.py

"""
تشخیص Swing High و Swing Low با رعایت عدم Look-ahead
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from ..types.market_structure import SwingPoint, SwingType


@dataclass
class SwingDetectorConfig:
    """پیکربندی تشخیص Swing"""
    pivot_left: int = 3  # تعداد کندل قبل از Swing
    pivot_right: int = 3  # تعداد کندل بعد از Swing برای تأیید
    min_swing_distance_pct: float = 0.001  # حداقل فاصله بین Swingها (0.1%)
    use_percentage_distance: bool = True
    
    def validate(self) -> List[str]:
        """اعتبارسنجی پیکربندی"""
        errors = []
        if self.pivot_left < 1:
            errors.append("pivot_left must be >= 1")
        if self.pivot_right < 1:
            errors.append("pivot_right must be >= 1")
        if self.min_swing_distance_pct <= 0:
            errors.append("min_swing_distance_pct must be > 0")
        return errors


class SwingDetector:
    """
    تشخیص Swing High و Swing Low از داده OHLCV
    
    این کلاس به صورت Causal عمل می‌کند:
    - Swingها فقط پس از pivot_right کندل تأیید می‌شوند
    - هیچ اطلاعاتی از آینده استفاده نمی‌شود
    """
    
    def __init__(self, config: Optional[SwingDetectorConfig] = None):
        self.config = config or SwingDetectorConfig()
        self._confirmed_swings: List[SwingPoint] = []
        self._pending_swings: List[Tuple[int, float, SwingType]] = []  # (index, price, type)
    
    def reset(self):
        """بازنشانی وضعیت detector"""
        self._confirmed_swings.clear()
        self._pending_swings.clear()
    
    def process_bar(self, ohlcv_data: List[dict], current_index: int) -> List[SwingPoint]:
        """
        پردازش کندل جاری و تشخیص Swingهای تأیید شده
        
        Args:
            ohlcv_data: لیست کندل‌های OHLCV
            current_index: ایندکس کندل جاری
        
        Returns:
            لیست Swingهای تأیید شده در این گام
        """
        newly_confirmed = []
        
        # بررسی Swingهای معلق برای تأیید
        confirmed_indices = []
        for pending_idx, pending_price, pending_type in self._pending_swings:
            # Swing فقط پس از pivot_right کندل تأیید می‌شود
            if current_index >= pending_idx + self.config.pivot_right:
                if self._is_swing_confirmed(ohlcv_data, pending_idx, pending_type):
                    swing = SwingPoint(
                        price=pending_price,
                        timestamp=ohlcv_data[pending_idx]['timestamp'],
                        swing_type=pending_type,
                        index=pending_idx,
                        is_confirmed=True,
                        confirmation_time=ohlcv_data[current_index]['timestamp']
                    )
                    
                    # بررسی فاصله از Swing قبلی
                    if self._is_valid_distance(swing):
                        self._confirmed_swings.append(swing)
                        newly_confirmed.append(swing)
                    
                    confirmed_indices.append(pending_idx)
        
        # حذف Swingهای تأیید شده از لیست معلق
        self._pending_swings = [
            (idx, price, stype) for idx, price, stype in self._pending_swings
            if idx not in confirmed_indices
        ]
        
        # بررسی کندل جاری برای Swing بالقوه
        self._check_potential_swing(ohlcv_data, current_index)
        
        return newly_confirmed
    
    def get_confirmed_swings(self) -> List[SwingPoint]:
        """دریافت تمام Swingهای تأیید شده"""
        return self._confirmed_swings.copy()
    
    def get_last_swing(self, swing_type: Optional[SwingType] = None) -> Optional[SwingPoint]:
        """دریافت آخرین Swing تأیید شده"""
        if swing_type:
            for swing in reversed(self._confirmed_swings):
                if swing.swing_type == swing_type:
                    return swing
        elif self._confirmed_swings:
            return self._confirmed_swings[-1]
        return None
    
    def _check_potential_swing(self, ohlcv_data: List[dict], index: int):
        """بررسی کندل برای Swing بالقوه"""
        if index < self.config.pivot_left:
            return
        
        current_high = ohlcv_data[index]['high']
        current_low = ohlcv_data[index]['low']
        
        # بررسی Swing High بالقوه
        is_potential_high = True
        for i in range(index - self.config.pivot_left, index):
            if ohlcv_data[i]['high'] >= current_high:
                is_potential_high = False
                break
        
        if is_potential_high:
            self._pending_swings.append((index, current_high, SwingType.HIGH))
        
        # بررسی Swing Low بالقوه
        is_potential_low = True
        for i in range(index - self.config.pivot_left, index):
            if ohlcv_data[i]['low'] <= current_low:
                is_potential_low = False
                break
        
        if is_potential_low:
            self._pending_swings.append((index, current_low, SwingType.LOW))
    
    def _is_swing_confirmed(self, ohlcv_data: List[dict], swing_index: int, swing_type: SwingType) -> bool:
        """بررسی تأیید Swing با کندل‌های بعدی"""
        swing_price = ohlcv_data[swing_index]['high'] if swing_type == SwingType.HIGH else ohlcv_data[swing_index]['low']
        
        # Swing باید pivot_right کندل بعدی را پشت سر بگذارد
        for i in range(swing_index + 1, min(swing_index + 1 + self.config.pivot_right, len(ohlcv_data))):
            if swing_type == SwingType.HIGH:
                if ohlcv_data[i]['high'] > swing_price:
                    return False
            else:  # LOW
                if ohlcv_data[i]['low'] < swing_price:
                    return False
        
        return True
    
    def _is_valid_distance(self, swing: SwingPoint) -> bool:
        """بررسی فاصله Swing از Swing قبلی"""
        if not self._confirmed_swings:
            return True
        
        last_swing = self._confirmed_swings[-1]
        
        if self.config.use_percentage_distance:
            if last_swing.price > 0:
                distance_pct = abs(swing.price - last_swing.price) / last_swing.price
                return distance_pct >= self.config.min_swing_distance_pct
        else:
            return abs(swing.price - last_swing.price) > 0
        
        return True
