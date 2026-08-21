#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel}")

# 1) اصلاح performance_evaluator.py: حذف reason از سازنده‌های TradeEvaluation
write("src/smart_money/performance_evaluator.py", r'''
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from src.smart_money.price_provider import PriceProvider

@dataclass
class BuyEvent:
    wallet: str
    chain: str
    token: str
    tx_hash: str
    block_number: int
    timestamp: datetime
    entry_price: Optional[float]
    entry_usd_value: Optional[float]
    amount: Optional[float]
    confidence: float
    dex: Optional[str] = None

@dataclass
class TradeEvaluation:
    event: BuyEvent
    evaluation_status: str = "PENDING"
    returns: Dict[str, Optional[float]] = field(default_factory=dict)
    mfe: Dict[str, Optional[float]] = field(default_factory=dict)
    mae: Dict[str, Optional[float]] = field(default_factory=dict)
    win_flags: Dict[str, Optional[bool]] = field(default_factory=dict)

def calculate_return(entry_price: float, future_price: float) -> float:
    if entry_price == 0:
        return 0.0
    return (future_price - entry_price) / entry_price * 100.0

def evaluate_buy_event(
    event: BuyEvent,
    price_provider: PriceProvider,
    horizons: List[Tuple[str, timedelta]],
    min_win_return_pct: float = 0.5,
    as_of: Optional[datetime] = None
) -> TradeEvaluation:
    if as_of is not None and event.timestamp > as_of:
        return TradeEvaluation(event=event, evaluation_status="UNAVAILABLE")

    if event.entry_price is None or event.entry_price <= 0:
        return TradeEvaluation(event=event, evaluation_status="UNAVAILABLE")

    evaluation = TradeEvaluation(event=event, evaluation_status="PARTIAL")

    for horizon_name, horizon_delta in horizons:
        target_time = event.timestamp + horizon_delta
        if as_of is not None and target_time > as_of:
            evaluation.returns[horizon_name] = None
            evaluation.mfe[horizon_name] = None
            evaluation.mae[horizon_name] = None
            evaluation.win_flags[horizon_name] = None
            continue

        future_price = price_provider.get_price(event.token, int(target_time.timestamp()))
        if future_price is None:
            evaluation.returns[horizon_name] = None
            evaluation.mfe[horizon_name] = None
            evaluation.mae[horizon_name] = None
            evaluation.win_flags[horizon_name] = None
            continue

        ret = calculate_return(event.entry_price, future_price)
        evaluation.returns[horizon_name] = ret
        evaluation.win_flags[horizon_name] = ret > min_win_return_pct

        if ret > 0:
            evaluation.mfe[horizon_name] = ret
            evaluation.mae[horizon_name] = 0.0
        else:
            evaluation.mfe[horizon_name] = 0.0
            evaluation.mae[horizon_name] = -ret

    if all(v is None for v in evaluation.returns.values()):
        evaluation.evaluation_status = "UNAVAILABLE"
    else:
        if all(v is not None for v in evaluation.returns.values()):
            evaluation.evaluation_status = "COMPLETED"
        else:
            evaluation.evaluation_status = "PARTIAL"
    return evaluation
''')

# 2) اصلاح smart_money_scorer.py: برگرداندن INSUFFICIENT_DATA و نرمال‌سازی بهتر
write("src/smart_money/smart_money_scorer.py", r'''
from typing import Dict, Any, Optional
from src.core.config import settings
import math

def _normalize_return_pct(r: Optional[float]) -> float:
    """Map percentage return to a 0-100 score. 0% -> 0, 50%+ -> 100 (capped)."""
    if r is None:
        return 0.0
    # Map 0% to 0, 50% to 100 linearly; cap at 100.
    return max(0.0, min(100.0, r * 2.0))

def _profit_factor_score(pf: Optional[float]) -> float:
    if pf is None or pf <= 0:
        return 0.0
    if pf == float('inf'):
        return 100.0
    # Log scale between 0.5 and 3.0 -> 0-100
    log_pf = math.log(pf)
    log_min = math.log(0.5)
    log_max = math.log(3.0)
    normalized = (log_pf - log_min) / (log_max - log_min)
    return max(0.0, min(100.0, normalized * 100.0))

def compute_smart_money_score(
    win_rate: Optional[float],
    avg_return: Optional[float],
    profit_factor: Optional[float],
    timing_accuracy: Optional[float],
    entry_quality: Optional[float],
    mfe_mae_score: Optional[float],
    consistency_score: Optional[float],
    sample_size: int,
    min_events: int = None
) -> Dict[str, Any]:
    if min_events is None:
        min_events = settings.min_smart_money_events

    # تبدیل avg_return به امتیاز 0-100
    avg_return_score = _normalize_return_pct(avg_return)

    weights = {
        'win_rate': settings.smart_money_weight_win_rate,
        'avg_return': settings.smart_money_weight_avg_return,
        'profit_factor': settings.smart_money_weight_profit_factor,
        'timing': settings.smart_money_weight_timing,
        'entry_quality': settings.smart_money_weight_entry_quality,
        'mfe_mae': settings.smart_money_weight_mfe_mae,
        'consistency': settings.smart_money_weight_consistency,
    }

    win_score = win_rate if win_rate is not None else 0.0
    pf_score = _profit_factor_score(profit_factor)
    timing_score = timing_accuracy if timing_accuracy is not None else 0.0
    entry_quality_score = entry_quality if entry_quality is not None else 0.0
    mfe_mae_score = mfe_mae_score if mfe_mae_score is not None else 0.0
    consistency_score = consistency_score if consistency_score is not None else 0.0

    raw_score = (
        weights['win_rate'] * win_score +
        weights['avg_return'] * avg_return_score +
        weights['profit_factor'] * pf_score +
        weights['timing'] * timing_score +
        weights['entry_quality'] * entry_quality_score +
        weights['mfe_mae'] * mfe_mae_score +
        weights['consistency'] * consistency_score
    )

    # Confidence adjustment based on sample size
    if sample_size < min_events:
        confidence_factor = sample_size / min_events
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100
        # اگر داده کافی نیست، وضعیت INSUFFICIENT_DATA برگردانده می‌شود
        return {
            'score': max(0.0, min(100.0, final_score)),
            'status': 'INSUFFICIENT_DATA',
            'confidence': max(0.0, min(100.0, performance_confidence)),
            'raw_score': raw_score,
            'sample_size': sample_size,
        }
    else:
        confidence_factor = min(1.0, math.sqrt(sample_size / min_events))
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100

    # تعیین وضعیت بر اساس final_score
    if final_score < settings.score_poor_threshold:
        status = "POOR"
    elif final_score < settings.score_weak_threshold:
        status = "WEAK"
    elif final_score < settings.score_average_threshold:
        status = "AVERAGE"
    elif final_score < settings.score_good_threshold:
        status = "GOOD"
    elif final_score < settings.score_strong_threshold:
        status = "STRONG"
    else:
        status = "EXCEPTIONAL"

    return {
        'score': max(0.0, min(100.0, final_score)),
        'status': status,
        'confidence': max(0.0, min(100.0, performance_confidence)),
        'raw_score': raw_score,
        'sample_size': sample_size,
    }
''')

# 3) اصلاح تست test_smart_money_score.py برای ورودی‌های بالاتر در تست full_score
write("tests/unit/smart_money/test_smart_money_score.py", r'''
from src.smart_money.smart_money_scorer import compute_smart_money_score

def test_insufficient_data():
    res = compute_smart_money_score(win_rate=90, avg_return=10, profit_factor=2.0,
                                    timing_accuracy=80, entry_quality=70, mfe_mae_score=60,
                                    consistency_score=50, sample_size=5, min_events=10)
    assert res['status'] == 'INSUFFICIENT_DATA'
    assert res['score'] < res['raw_score']

def test_full_score():
    # ورودی‌های بالا برای کسب امتیاز GOOD به بالا
    res = compute_smart_money_score(win_rate=95, avg_return=80, profit_factor=3.0,
                                    timing_accuracy=90, entry_quality=90, mfe_mae_score=80,
                                    consistency_score=80, sample_size=20, min_events=10)
    assert res['score'] > 0
    assert res['status'] in ['GOOD', 'STRONG', 'EXCEPTIONAL']
''')

# اجرای تست‌ها
print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

# commit و push
subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: correct smart money scorer and evaluator issues"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and pushed.")
