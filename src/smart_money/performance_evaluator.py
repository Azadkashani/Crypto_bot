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
