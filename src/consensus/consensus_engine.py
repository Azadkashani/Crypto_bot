from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, UTC
from collections import defaultdict
from src.core.config import settings
from src.storage.models import WhaleConsensus
import math

class ConsensusEngine:
    def __init__(self, window_minutes: int = None):
        self.window_minutes = window_minutes or settings.consensus_window_minutes

    def _window_start(self, timestamp: datetime) -> datetime:
        epoch = datetime(1970,1,1,tzinfo=UTC)
        delta = int((timestamp - epoch).total_seconds() // (self.window_minutes * 60))
        return epoch + timedelta(seconds=delta * self.window_minutes * 60)

    def _filter_excluded(self, events: List[Dict[str, Any]], excluded_registry) -> List[Dict[str, Any]]:
        if not excluded_registry:
            return events
        return [e for e in events if not excluded_registry.is_excluded(e.get('wallet', ''))]

    def _deduplicate_wallets(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for e in events:
            addr = e.get('wallet')
            if addr and addr not in seen:
                seen.add(addr)
                deduped.append(e)
        return deduped

    def compute_consensus(
        self,
        chain: str,
        token: str,
        events: List[Dict[str, Any]],
        as_of: Optional[datetime] = None,
        excluded_registry = None,
    ) -> Optional[WhaleConsensus]:
        if not events:
            return None

        if as_of is not None:
            events = [e for e in events if e['timestamp'] <= as_of]

        if not events:
            return None

        events = self._filter_excluded(events, excluded_registry)
        events = self._deduplicate_wallets(events)

        if not events:
            return None

        buys = [e for e in events if e.get('side') == 'BUY']
        sells = [e for e in events if e.get('side') == 'SELL']

        total_buy_volume = sum(e.get('usd_value', 0.0) or 0.0 for e in buys)
        total_sell_volume = sum(e.get('usd_value', 0.0) or 0.0 for e in sells)
        net_flow = total_buy_volume - total_sell_volume

        unique_buying_wallets = len(set(e.get('wallet') for e in buys if e.get('wallet')))
        unique_selling_wallets = len(set(e.get('wallet') for e in sells if e.get('wallet')))

        independent_buying_whales = unique_buying_wallets
        independent_selling_whales = unique_selling_wallets

        buy_event_count = len(buys)
        sell_event_count = len(sells)

        avg_whale_score = sum(e.get('whale_score', 0) or 0 for e in events) / len(events) if events else 0
        avg_smart_money_score = sum(e.get('smart_money_score', 0) or 0 for e in events) / len(events) if events else 0

        total_volume = total_buy_volume + total_sell_volume
        if total_volume > 0:
            weighted_whale = sum((e.get('whale_score', 0) or 0) * (e.get('usd_value', 0) or 0) for e in events) / total_volume
            weighted_smart = sum((e.get('smart_money_score', 0) or 0) * (e.get('usd_value', 0) or 0) for e in events) / total_volume
        else:
            weighted_whale = avg_whale_score
            weighted_smart = avg_smart_money_score

        timestamps = [e['timestamp'] for e in events]
        time_span_seconds = (max(timestamps) - min(timestamps)).total_seconds()
        window_seconds = self.window_minutes * 60
        temporal_convergence = max(0.0, 1.0 - (time_span_seconds / window_seconds)) * 100 if window_seconds > 0 else 100.0

        total_events = buy_event_count + sell_event_count
        if total_events > 0:
            agreement_raw = (buy_event_count - sell_event_count) / total_events
            whale_agreement = ((agreement_raw + 1) / 2) * 100
        else:
            whale_agreement = 50.0

        if total_sell_volume > 0:
            buy_sell_ratio = total_buy_volume / total_sell_volume
            if buy_sell_ratio >= 1:
                volume_strength = min(100.0, 50.0 + math.log10(buy_sell_ratio) * 50)
            else:
                volume_strength = max(0.0, 50.0 - math.log10(1/buy_sell_ratio) * 50)
        else:
            volume_strength = 100.0 if total_buy_volume > 0 else 0.0

        breadth_buy = min(100.0, (independent_buying_whales / settings.min_independent_whales) * 100) if settings.min_independent_whales > 0 else 100.0
        breadth_sell = min(100.0, (independent_selling_whales / settings.min_independent_whales) * 100) if settings.min_independent_whales > 0 else 100.0
        wallet_breadth = max(breadth_buy, breadth_sell) if independent_buying_whales > 0 else 0.0

        confidences = [e.get('confidence', 0) or 0 for e in events]
        data_quality_score = sum(confidences) / len(confidences) if confidences else 0.0

        score = (
            settings.consensus_weight_independent_count * min(100.0, independent_buying_whales * 20) +
            settings.consensus_weight_net_flow * min(100.0, (net_flow / settings.min_net_flow_usd) * 100) +
            settings.consensus_weight_buy_sell_ratio * min(100.0, volume_strength) +
            settings.consensus_weight_avg_whale_score * avg_whale_score +
            settings.consensus_weight_avg_smart_money_score * avg_smart_money_score +
            settings.consensus_weight_temporal_convergence * temporal_convergence +
            settings.consensus_weight_whale_agreement * whale_agreement
        )
        score = max(0.0, min(100.0, score))

        if net_flow > 0 and independent_buying_whales >= settings.min_independent_whales:
            direction = "BULLISH"
        elif net_flow < 0 and independent_selling_whales >= settings.min_independent_whales:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        sample_factor = min(1.0, (independent_buying_whales + independent_selling_whales) / (2 * settings.min_independent_whales))
        confidence = min(100.0, (data_quality_score * 0.5 + sample_factor * 50) * (whale_agreement / 100))

        if independent_buying_whales < settings.min_independent_whales and independent_selling_whales < settings.min_independent_whales:
            status = "INSUFFICIENT_SAMPLE"
        elif confidence < settings.min_consensus_confidence or score < settings.min_consensus_score:
            status = "WEAK"
        else:
            status = "VALID"

        window_start = self._window_start(min(timestamps))
        window_end = window_start + timedelta(minutes=self.window_minutes)

        consensus = WhaleConsensus(
            token=token,
            chain=chain,
            window_start=window_start,
            window_end=window_end,
            total_buy_volume=total_buy_volume,
            total_sell_volume=total_sell_volume,
            net_whale_flow=net_flow,
            unique_buying_wallets=unique_buying_wallets,
            unique_selling_wallets=unique_selling_wallets,
            independent_buying_whales=independent_buying_whales,
            independent_selling_whales=independent_selling_whales,
            buy_event_count=buy_event_count,
            sell_event_count=sell_event_count,
            average_whale_score=avg_whale_score,
            weighted_whale_score=weighted_whale,
            average_smart_money_score=avg_smart_money_score,
            weighted_smart_money_score=weighted_smart,
            temporal_convergence_score=temporal_convergence,
            whale_agreement_score=whale_agreement,
            wallet_breadth_score=wallet_breadth,
            volume_strength_score=volume_strength,
            consensus_score=score,
            confidence=confidence,
            direction=direction,
            status=status,
            data_quality_score=data_quality_score,
            components={
                "weights": {
                    "independent_count": settings.consensus_weight_independent_count,
                    "net_flow": settings.consensus_weight_net_flow,
                    "buy_sell_ratio": settings.consensus_weight_buy_sell_ratio,
                    "avg_whale_score": settings.consensus_weight_avg_whale_score,
                    "avg_smart_money_score": settings.consensus_weight_avg_smart_money_score,
                    "temporal_convergence": settings.consensus_weight_temporal_convergence,
                    "whale_agreement": settings.consensus_weight_whale_agreement,
                },
                "total_volume": total_buy_volume + total_sell_volume,
                "time_span_seconds": time_span_seconds,
            }
        )
        return consensus
