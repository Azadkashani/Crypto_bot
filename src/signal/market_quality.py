from typing import Dict, Any, Optional

class MarketQuality:
    def __init__(self):
        pass

    def compute_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        data must contain:
        - volume_24h
        - liquidity
        - atr (or volatility)
        - volume_consistency (optional)
        - gate_available
        Returns score (0-100) and components.
        """
        volume_24h = data.get('volume_24h', 0) or 0
        liquidity = data.get('liquidity', 0) or 0
        volatility = data.get('volatility', None)
        gate_available = data.get('gate_available', False)
        volume_consistency = data.get('volume_consistency', 50.0)  # default neutral

        # Volume score: log scale, assume $500k minimum, $10M is good
        import math
        if volume_24h <= 0:
            volume_score = 0
        else:
            log_vol = math.log10(volume_24h)
            # Map $100k -> 0, $10M -> 100
            min_vol = math.log10(100_000)
            max_vol = math.log10(10_000_000)
            volume_score = ((log_vol - min_vol) / (max_vol - min_vol)) * 100
            volume_score = max(0, min(100, volume_score))

        # Liquidity score: similar log scale, assume $100k -> 0, $5M -> 100
        if liquidity <= 0:
            liquidity_score = 0
        else:
            log_liq = math.log10(liquidity)
            min_liq = math.log10(100_000)
            max_liq = math.log10(5_000_000)
            liquidity_score = ((log_liq - min_liq) / (max_liq - min_liq)) * 100
            liquidity_score = max(0, min(100, liquidity_score))

        # Volatility score: if None, neutral 50
        if volatility is None:
            volatility_score = 50.0
        else:
            # Assume volatility as percentage; optimal around 1-3%
            if volatility <= 0:
                volatility_score = 0
            elif volatility < 1:
                volatility_score = 80  # low volatility, easier entry
            elif volatility < 3:
                volatility_score = 70
            elif volatility < 5:
                volatility_score = 50
            elif volatility < 10:
                volatility_score = 30
            else:
                volatility_score = 10

        # Volume consistency: already 0-100
        consistency_score = max(0, min(100, volume_consistency))

        # Gate availability bonus
        gate_bonus = 20 if gate_available else 0

        overall_score = 0.3*volume_score + 0.3*liquidity_score + 0.2*volatility_score + 0.1*consistency_score + 0.1*gate_bonus
        overall_score = max(0, min(100, overall_score))

        return {
            'score': overall_score,
            'components': {
                'volume_score': volume_score,
                'liquidity_score': liquidity_score,
                'volatility_score': volatility_score,
                'consistency_score': consistency_score,
                'gate_available': gate_available,
            }
        }
