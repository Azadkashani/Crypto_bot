import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC

class GatePublicData:
    """Fetch public market data from Gate.io (no authentication required)."""
    def __init__(self, base_url: str = "https://api.gateio.ws/api/v4", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _get(self, path: str, params: dict = None) -> Any:
        url = f"{self.base_url}{path}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_futures_candlesticks(
        self,
        contract: str,
        interval: str = "5m",
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get OHLCV candlesticks for a USDT-M perpetual futures contract.
        contract example: "BTC_USDT"
        interval: e.g., 1m, 5m, 15m, 1h, 4h, 1d
        Returns list of candles with keys: t (timestamp), o, h, l, c, v.
        """
        params = {
            "contract": contract,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["from"] = start_time
        if end_time:
            params["to"] = end_time

        candles = await self._get("/futures/usdt/candlesticks", params=params)
        return candles

    async def get_futures_contracts(self) -> List[Dict[str, Any]]:
        """List all USDT-M perpetual contracts."""
        return await self._get("/futures/usdt/contracts")

    async def get_futures_ticker(self, contract: str) -> Dict[str, Any]:
        """Get ticker for a specific contract."""
        return await self._get(f"/futures/usdt/tickers/{contract}")

    async def close(self):
        await self._client.aclose()
