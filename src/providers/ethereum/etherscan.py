import asyncio
import httpx
from typing import List, Dict, Any, Callable, Optional
from src.providers.base import BaseDataProvider
from src.core.constants import Chain
from src.core.config import settings

class EtherscanProvider(BaseDataProvider):
    name = "etherscan"
    chain = Chain.ETHEREUM

    def __init__(self, api_key: Optional[str] = None, base_url: str = None, timeout: int = 30, max_retries: int = 5):
        self.api_key = api_key or settings.eth_etherscan_api_key
        self.base_url = base_url or settings.eth_etherscan_base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {**params, "apikey": self.api_key}
        for attempt in range(self.max_retries):
            try:
                response = await self._client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])
                else:
                    # Etherscan error, maybe rate limit
                    if data.get("message", "").startswith("NOTOK"):
                        if "rate limit" in data.get("result", "").lower():
                            await asyncio.sleep(2 ** attempt)  # simple backoff
                            continue
                        else:
                            raise Exception(f"Etherscan error: {data.get('result')}")
                    else:
                        return data.get("result", [])
            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)
        raise Exception("Max retries exceeded")

    async def fetch_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "asc",
        }
        result = await self._make_request(params)
        return result if isinstance(result, list) else []

    async def fetch_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "contractaddress": token,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "asc",
        }
        result = await self._make_request(params)
        return result if isinstance(result, list) else []

    async def fetch_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        # Etherscan doesn't provide swap events directly; would need specific topic filter via eth_getLogs.
        return []

    async def stream_blocks(self, callback: Callable[[Dict[str, Any]], None]):
        # Not applicable for Etherscan (HTTP only). Use RPC/WS.
        raise NotImplementedError("Etherscan does not support streaming. Use WebSocket RPC.")

    async def stream_logs(self, topics: List[str], callback: Callable[[Dict[str, Any]], None]):
        raise NotImplementedError("Etherscan does not support streaming. Use WebSocket RPC.")

    async def fetch_token_price(self, token: str, timestamp: int) -> float:
        # Could use Etherscan API for token price? Not directly. Placeholder.
        raise NotImplementedError

    async def fetch_market_cap(self, token: str) -> float:
        raise NotImplementedError

    async def close(self):
        await self._client.aclose()
