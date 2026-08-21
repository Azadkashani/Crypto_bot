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

# اصلاح signal_generator.py: فیلتر کردن دیتافریم تا timestamp قبل از استفاده
write("src/signal/signal_generator.py", r'''
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.core.config import settings
from src.signal.market_confirmation import MarketConfirmation
from src.signal.entry_timing import EntryTiming
from src.signal.market_quality import MarketQuality
from src.signal.gate_validator import GateValidator
import json

class SignalGenerator:
    def __init__(self):
        self.market_confirmation = MarketConfirmation()
        self.entry_timing = EntryTiming()
        self.market_quality = MarketQuality()
        self.gate_validator = GateValidator()

    def generate_signal(
        self,
        whale_consensus: Dict[str, Any],
        market_data_df: Any,  # pandas DataFrame with OHLCV
        token_symbol: str,
        chain: str,
        timestamp: datetime,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Validate weights
        if not settings.validate_signal_weights():
            return {
                'direction': 'REJECTED',
                'status': 'INVALID_CONFIG',
                'rejection_reasons': ['Signal weights do not sum to 1.0'],
                'signal_score': 0.0,
                'confidence': 0.0,
            }

        # فیلتر کردن داده‌های بازار تا timestamp مشخص برای جلوگیری از Look-Ahead
        if timestamp is not None:
            market_data = market_data_df[market_data_df['timestamp'] <= timestamp].copy()
        else:
            market_data = market_data_df.copy()
        market_data = market_data.sort_values('timestamp').reset_index(drop=True)

        # Extract whale metrics
        consensus_score = whale_consensus.get('consensus_score', 0) or 0
        consensus_confidence = whale_consensus.get('confidence', 0) or 0
        consensus_direction = whale_consensus.get('direction', 'NEUTRAL')
        smart_money_score = whale_consensus.get('average_smart_money_score', 0) or 0
        net_whale_flow = whale_consensus.get('net_whale_flow', 0) or 0
        independent_buying = whale_consensus.get('independent_buying_whales', 0) or 0
        independent_selling = whale_consensus.get('independent_selling_whales', 0) or 0
        independent_whales = independent_buying if consensus_direction == 'BULLISH' else independent_selling

        # Market confirmation (use filtered data)
        market_result = self.market_confirmation.score_market(market_data, timestamp)
        market_score = market_result['score']
        market_direction = market_result['direction']
        market_confidence = market_result['confidence']

        # Entry timing (use filtered data)
        entry_timing_result = self.entry_timing.compute_score(market_data, timestamp)
        entry_timing_score = entry_timing_result['score']

        # Gate validation
        gate_available = self.gate_validator.is_futures_available(token_symbol)

        # Market quality: use last row of filtered data
        if market_data.empty:
            last_candle = None
        else:
            last_candle = market_data.iloc[-1]
        volume_24h = last_candle.get('volume_24h', 0) if last_candle is not None and 'volume_24h' in last_candle else 0
        # اگر ستون volume_24h وجود ندارد، از حجم آخرین کندل به عنوان تقریبی استفاده می‌کنیم
        if volume_24h == 0 and last_candle is not None and 'volume' in last_candle:
            volume_24h = last_candle['volume'] * 24  # خیلی ساده
        liquidity = extra_data.get('liquidity', 0) if extra_data else 0
        volatility = extra_data.get('volatility', None) if extra_data else None
        volume_consistency = 50.0  # default
        if extra_data and 'volume_consistency' in extra_data:
            volume_consistency = extra_data['volume_consistency']

        quality_input = {
            'volume_24h': volume_24h,
            'liquidity': liquidity,
            'volatility': volatility,
            'gate_available': gate_available,
            'volume_consistency': volume_consistency,
        }
        quality_result = self.market_quality.compute_score(quality_input)
        quality_score = quality_result['score']
        liquidity_score = quality_result['components']['liquidity_score']
        volume_score = quality_result['components']['volume_score']
        volatility_score = quality_result['components']['volatility_score']

        # Conflict detection
        conflict_detected = False
        conflict_reason = ""
        if consensus_direction == 'BULLISH' and market_direction == 'bearish':
            conflict_detected = True
            conflict_reason = "Whale consensus bullish but market bearish"
        elif consensus_direction == 'BEARISH' and market_direction == 'bullish':
            conflict_detected = True
            conflict_reason = "Whale consensus bearish but market bullish"

        # Score components
        whale_consensus_norm = min(100, consensus_score)
        smart_money_norm = min(100, smart_money_score)
        if settings.min_net_flow_usd > 0:
            net_flow_norm = min(100, (abs(net_whale_flow) / settings.min_net_flow_usd) * 100) if net_whale_flow > 0 else 0
        else:
            net_flow_norm = 0
        independent_norm = min(100, (independent_whales / settings.min_independent_whales) * 100) if settings.min_independent_whales > 0 else 0
        market_confirm_norm = market_score
        liquidity_norm = liquidity_score
        volume_norm = volume_score
        entry_timing_norm = entry_timing_score
        market_quality_norm = quality_score

        signal_score = (
            settings.signal_weight_whale_consensus * whale_consensus_norm +
            settings.signal_weight_smart_money * smart_money_norm +
            settings.signal_weight_net_whale_flow * net_flow_norm +
            settings.signal_weight_independent_whales * independent_norm +
            settings.signal_weight_market_confirmation * market_confirm_norm +
            settings.signal_weight_liquidity * liquidity_norm +
            settings.signal_weight_volume * volume_norm +
            settings.signal_weight_entry_timing * entry_timing_norm +
            settings.signal_weight_market_quality * market_quality_norm
        )
        signal_score = max(0, min(100, signal_score))

        # Confidence
        data_quality = whale_consensus.get('data_quality_score', 0) or 0
        sample_factor = min(1.0, (independent_whales / settings.min_independent_whales)) if settings.min_independent_whales > 0 else 0
        agreement_factor = 100 if not conflict_detected else 20
        confidence = (data_quality * 0.3 + sample_factor * 50 + market_confidence * 0.2) * (agreement_factor / 100)
        confidence = max(0, min(100, confidence))

        # Determine direction and status
        direction = 'NEUTRAL'
        rejection_reasons = []

        critical_fail = False
        if conflict_detected:
            critical_fail = True
            rejection_reasons.append(conflict_reason)
        if not gate_available:
            critical_fail = True
            rejection_reasons.append("Token not available on Gate.io USDT-M Perpetual")
        if consensus_score < settings.min_consensus_score or consensus_confidence < settings.min_consensus_confidence:
            critical_fail = True
            rejection_reasons.append("Whale consensus score/confidence below threshold")
        if independent_whales < settings.min_independent_whales:
            critical_fail = True
            rejection_reasons.append("Insufficient independent whales")
        if quality_score < settings.min_liquidity_score or volume_score < settings.min_volume_score:
            critical_fail = True
            rejection_reasons.append("Low liquidity/volume")
        if volatility_score < settings.min_volatility_score or volatility_score > settings.max_volatility_score:
            critical_fail = True
            rejection_reasons.append("Volatility out of acceptable range")
        if consensus_direction == 'BULLISH' and market_score < settings.market_confirm_bullish_threshold:
            critical_fail = True
            rejection_reasons.append("Market confirmation not bullish enough for LONG")
        if consensus_direction == 'BEARISH' and market_score > settings.market_confirm_bearish_threshold:
            critical_fail = True
            rejection_reasons.append("Market confirmation not bearish enough for SHORT")

        if critical_fail:
            status = 'REJECTED'
            direction = 'REJECTED'
        else:
            if consensus_direction == 'BULLISH' and market_direction in ['bullish', 'neutral']:
                direction = 'LONG'
            elif consensus_direction == 'BEARISH' and market_direction in ['bearish', 'neutral']:
                direction = 'SHORT'
            else:
                direction = 'NEUTRAL'
                status = 'CONFLICTED' if conflict_detected else 'INSUFFICIENT_DATA'

            if direction != 'NEUTRAL':
                if signal_score >= settings.signal_min_score and confidence >= settings.signal_min_confidence:
                    status = 'VALID'
                elif signal_score >= settings.signal_min_score:
                    status = 'WATCH'
                else:
                    status = 'INSUFFICIENT_DATA'

        if status not in ['REJECTED', 'VALID', 'WATCH', 'CONFLICTED', 'INSUFFICIENT_DATA']:
            status = 'INSUFFICIENT_DATA'

        components = {
            'whale_consensus_score': consensus_score,
            'whale_consensus_confidence': consensus_confidence,
            'smart_money_score': smart_money_score,
            'net_whale_flow': net_whale_flow,
            'independent_whales': independent_whales,
            'market_confirmation_score': market_score,
            'market_direction': market_direction,
            'entry_timing_score': entry_timing_score,
            'liquidity_score': liquidity_score,
            'volume_score': volume_score,
            'volatility_score': volatility_score,
            'gate_available': gate_available,
            'conflict_detected': conflict_detected,
            'conflict_reason': conflict_reason,
            'weights': {
                'whale_consensus': settings.signal_weight_whale_consensus,
                'smart_money': settings.signal_weight_smart_money,
                'net_whale_flow': settings.signal_weight_net_whale_flow,
                'independent_whales': settings.signal_weight_independent_whales,
                'market_confirmation': settings.signal_weight_market_confirmation,
                'liquidity': settings.signal_weight_liquidity,
                'volume': settings.signal_weight_volume,
                'entry_timing': settings.signal_weight_entry_timing,
                'market_quality': settings.signal_weight_market_quality,
            }
        }

        return {
            'direction': direction,
            'signal_score': signal_score,
            'confidence': confidence,
            'status': status,
            'rejection_reasons': rejection_reasons,
            'components': components,
            'whale_consensus_score': consensus_score,
            'whale_consensus_confidence': consensus_confidence,
            'smart_money_score': smart_money_score,
            'net_whale_flow': net_whale_flow,
            'independent_whales': independent_whales,
            'market_confirmation_score': market_score,
            'entry_timing_score': entry_timing_score,
            'liquidity_score': liquidity_score,
            'volume_score': volume_score,
            'volatility_score': volatility_score,
            'gate_available': gate_available,
            'conflict_detected': conflict_detected,
            'token_symbol': token_symbol,
            'chain': chain,
            'timestamp': timestamp,
        }
''')

print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: filter market data by timestamp in signal generator to prevent look-ahead"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and pushed.")
