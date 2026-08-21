from typing import Optional

class GateValidator:
    """Validates if a token is tradable on Gate.io USDT-M Perpetual Futures.
    In research mode, we can use a static list or later implement public API call."""
    def __init__(self):
        # Static set of known tokens available on Gate USDT-M Perpetual (for demo)
        # In production, this could be fetched from public API.
        self._available_tokens = {
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "MATIC", "AVAX", "LINK",
            "UNI", "AAVE", "SUSHI", "CRV", "SNX", "COMP", "MKR", "LTC", "BCH", "EOS",
        }

    def is_futures_available(self, token_symbol: str) -> bool:
        """Check if a token has USDT-M Perpetual on Gate.io."""
        if not token_symbol:
            return False
        return token_symbol.upper() in self._available_tokens

    def get_market_data(self, token_symbol: str) -> Optional[dict]:
        """Placeholder: return None since we don't fetch market data in this phase."""
        return None
