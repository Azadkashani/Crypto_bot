from src.collectors.backfill import BackfillEngine
from src.blockchain.ethereum import EthereumAdapter
from src.providers.ethereum.rpc_provider import EthereumRpcProvider
from src.providers.ethereum.etherscan import EtherscanProvider
from src.core.config import settings

async def main():
    rpc = EthereumRpcProvider()
    adapter = EthereumAdapter(rpc)
    # Optionally use Etherscan for historical (but we won't for now)
    engine = BackfillEngine(adapter)
    await engine.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
