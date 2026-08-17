"""
مدیریت ریسک و محاسبه حجم معاملات
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PositionSize:
    """کلاس نگهداری اطلاعات حجم معامله"""
    position_size: float      # حجم معامله به USDT
    risk_amount: float        # مقدار ریسک به USDT
    stop_loss_pct: float      # درصد حد ضرر
    take_profit_pct: float    # درصد حد سود
    leverage: int             # لوریج
    risk_reward_ratio: float  # نسبت ریسک به ریوارد
    margin_required: float    # مارجین مورد نیاز

class RiskManager:
    """
    مدیریت ریسک و محاسبه حجم معاملات
    """
    
    def __init__(self, config: Dict = None):
        """
        مقداردهی اولیه
        
        Parameters:
        -----------
        config : Dict
            تنظیمات مدیریت ریسک
        """
        self.config = {
            # محدودیتها
            'max_positions': 4,              # حداکثر ۴ معامله همزمان
            'position_size_percent': 25,     # ۲۵٪ موجودی برای هر معامله
            'max_positions_per_coin': 1,     # یک پوزیشن روی هر ارز
            
            # ریسک
            'risk_per_trade_percent': 1,     # ۱٪ ریسک از کل سرمایه
            'risk_per_position_percent': 4,  # ۴٪ ریسک از حجم معامله
            
            # نسبت ریسک به ریوارد
            'min_risk_reward': 2.0,          # حداقل نسبت ۲:۱
            
            # لوریج
            'max_leverage': 20,              # حداکثر لوریج
            'min_leverage': 1,               # حداقل لوریج
            
            # حد ضرر و سود
            'atr_mult_sl': 2.5,              # ضریب ATR برای حد ضرر
            'atr_mult_tp': 4.0,              # ضریب ATR برای حد سود
        }
        
        if config:
            self.config.update(config)
    
    def calculate_position_size(self, total_balance: float) -> float:
        """
        محاسبه حجم معامله (۲۵٪ موجودی کل)
        
        Parameters:
        -----------
        total_balance : float
            موجودی کل فیوچرز
            
        Returns:
        --------
        float
            حجم معامله به USDT
        """
        position_size = total_balance * (self.config['position_size_percent'] / 100)
        return position_size
    
    def calculate_risk_amount(self, total_balance: float) -> float:
        """
        محاسبه مقدار ریسک (۱٪ از کل سرمایه)
        
        Parameters:
        -----------
        total_balance : float
            موجودی کل فیوچرز
            
        Returns:
        --------
        float
            مقدار ریسک به USDT
        """
        risk_amount = total_balance * (self.config['risk_per_trade_percent'] / 100)
        return risk_amount
    
    def calculate_stop_loss_pct(self, entry_price: float, stop_loss_price: float) -> float:
        """
        محاسبه درصد حد ضرر
        
        Parameters:
        -----------
        entry_price : float
            قیمت ورود
        stop_loss_price : float
            قیمت حد ضرر
            
        Returns:
        --------
        float
            درصد حد ضرر (مثلاً 0.5 یعنی ۰.۵٪)
        """
        if entry_price <= 0:
            return 0
        
        stop_loss_pct = abs(entry_price - stop_loss_price) / entry_price * 100
        return stop_loss_pct
    
    def calculate_take_profit_pct(self, entry_price: float, take_profit_price: float) -> float:
        """
        محاسبه درصد حد سود
        
        Parameters:
        -----------
        entry_price : float
            قیمت ورود
        take_profit_price : float
            قیمت حد سود
            
        Returns:
        --------
        float
            درصد حد سود
        """
        if entry_price <= 0:
            return 0
        
        take_profit_pct = abs(take_profit_price - entry_price) / entry_price * 100
        return take_profit_pct
    
    def calculate_leverage(self, stop_loss_pct: float, risk_per_position_pct: float = None) -> int:
        """
        محاسبه لوریج بر اساس درصد حد ضرر
        
        فرمول:
        leverage = risk_per_position_pct / stop_loss_pct
        
        مثال:
        اگر حد ضرر ۰.۵٪ و ریسک ۴٪ باشد:
        leverage = 4 / 0.5 = 8
        
        Parameters:
        -----------
        stop_loss_pct : float
            درصد حد ضرر
        risk_per_position_pct : float
            درصد ریسک از حجم معامله (پیشفرض: ۴٪)
            
        Returns:
        --------
        int
            لوریج محاسبه شده
        """
        if risk_per_position_pct is None:
            risk_per_position_pct = self.config['risk_per_position_percent']
        
        if stop_loss_pct <= 0:
            return self.config['max_leverage']
        
        # محاسبه لوریج
        leverage = risk_per_position_pct / stop_loss_pct
        
        # محدود کردن به حداقل و حداکثر
        leverage = max(self.config['min_leverage'], min(leverage, self.config['max_leverage']))
        
        # گرد کردن به عدد صحیح
        return int(leverage)
    
    def calculate_risk_reward_ratio(self, stop_loss_pct: float, take_profit_pct: float) -> float:
        """
        محاسبه نسبت ریسک به ریوارد
        
        Parameters:
        -----------
        stop_loss_pct : float
            درصد حد ضرر
        take_profit_pct : float
            درصد حد سود
            
        Returns:
        --------
        float
            نسبت ریسک به ریوارد
        """
        if stop_loss_pct <= 0:
            return 0
        
        return take_profit_pct / stop_loss_pct
    
    def is_valid_trade(self, position_size: float, risk_reward_ratio: float) -> bool:
        """
        بررسی اعتبار معامله
        
        Parameters:
        -----------
        position_size : float
            حجم معامله
        risk_reward_ratio : float
            نسبت ریسک به ریوارد
            
        Returns:
        --------
        bool
            آیا معامله معتبر است؟
        """
        # بررسی نسبت ریسک به ریوارد
        if risk_reward_ratio < self.config['min_risk_reward']:
            return False
        
        # بررسی حجم معامله
        if position_size <= 0:
            return False
        
        return True
    
    def check_position_limits(self, open_positions: List[Dict], new_coin: str) -> Dict:
        """
        بررسی محدودیتهای پوزیشن
        
        Parameters:
        -----------
        open_positions : List[Dict]
            لیست پوزیشنهای باز
        new_coin : str
            ارز جدید برای معامله
            
        Returns:
        --------
        Dict
            نتیجه بررسی
        """
        # بررسی تعداد پوزیشنهای باز
        if len(open_positions) >= self.config['max_positions']:
            return {
                'allowed': False,
                'reason': f'حداکثر {self.config["max_positions"]} معامله همزمان مجاز است'
            }
        
        # بررسی پوزیشن تکراری روی همان ارز
        for pos in open_positions:
            if pos.get('contract') == new_coin:
                return {
                    'allowed': False,
                    'reason': f'پوزیشن باز روی {new_coin} وجود دارد'
                }
        
        return {
            'allowed': True,
            'reason': 'مجاز'
        }
    
    def calculate_full_position(self, 
                                total_balance: float,
                                entry_price: float,
                                stop_loss_price: float,
                                take_profit_price: float) -> Optional[PositionSize]:
        """
        محاسبه کامل مشخصات معامله
        
        Parameters:
        -----------
        total_balance : float
            موجودی کل فیوچرز
        entry_price : float
            قیمت ورود
        stop_loss_price : float
            قیمت حد ضرر
        take_profit_price : float
            قیمت حد سود
            
        Returns:
        --------
        PositionSize
            اطلاعات کامل حجم معامله
        """
        # محاسبه حجم معامله (۲۵٪ موجودی)
        position_size = self.calculate_position_size(total_balance)
        
        # محاسبه مقدار ریسک (۱٪ موجودی)
        risk_amount = self.calculate_risk_amount(total_balance)
        
        # محاسبه درصد حد ضرر
        stop_loss_pct = self.calculate_stop_loss_pct(entry_price, stop_loss_price)
        
        # محاسبه درصد حد سود
        take_profit_pct = self.calculate_take_profit_pct(entry_price, take_profit_price)
        
        # محاسبه نسبت ریسک به ریوارد
        rr_ratio = self.calculate_risk_reward_ratio(stop_loss_pct, take_profit_pct)
        
        # بررسی اعتبار معامله
        if not self.is_valid_trade(position_size, rr_ratio):
            logger.warning(f"⚠️ معامله نامعتبر - RR: {rr_ratio:.2f}")
            return None
        
        # محاسبه لوریج
        leverage = self.calculate_leverage(stop_loss_pct)
        
        # محاسبه مارجین مورد نیاز
        margin_required = position_size / leverage
        
        return PositionSize(
            position_size=position_size,
            risk_amount=risk_amount,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            leverage=leverage,
            risk_reward_ratio=rr_ratio,
            margin_required=margin_required,
        )
