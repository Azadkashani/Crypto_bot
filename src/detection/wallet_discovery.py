from collections import defaultdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.dex.models import NormalizedSwap

class WalletAggregator:
    def __init__(self, swaps: List[NormalizedSwap], as_of: Optional[datetime] = None):
        self.swaps = swaps
        self.as_of = as_of

    def _filter_swaps_by_time(self):
        if self.as_of is None:
            return self.swaps
        return [s for s in self.swaps if s.timestamp <= self.as_of]

    def aggregate(self) -> Dict[str, Dict[str, Any]]:
        filtered = self._filter_swaps_by_time()
        wallet_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'chain': 'ethereum', 'address': '', 'first_seen': None, 'last_seen': None,
            'total_volume_usd': 0.0, 'buy_volume_usd': 0.0, 'sell_volume_usd': 0.0,
            'net_flow_usd': 0.0, 'swap_count': 0, 'buy_count': 0, 'sell_count': 0,
            'largest_trade_size_usd': 0.0, 'unique_tokens': set(), 'unique_dexes': set(),
            'address_type': 'unknown',
        })

        for swap in filtered:
            if swap.side not in ['BUY', 'SELL']:
                continue
            addr = swap.wallet_address
            stats = wallet_stats[addr]
            if stats['first_seen'] is None or swap.timestamp < stats['first_seen']:
                stats['first_seen'] = swap.timestamp
            if stats['last_seen'] is None or swap.timestamp > stats['last_seen']:
                stats['last_seen'] = swap.timestamp

            trade_size = swap.usd_value if swap.usd_value is not None else 0.0
            stats['total_volume_usd'] += trade_size
            if swap.side == 'BUY':
                stats['buy_volume_usd'] += trade_size
                stats['buy_count'] += 1
            else:
                stats['sell_volume_usd'] += trade_size
                stats['sell_count'] += 1
            stats['net_flow_usd'] = stats['buy_volume_usd'] - stats['sell_volume_usd']
            stats['swap_count'] += 1
            stats['largest_trade_size_usd'] = max(stats['largest_trade_size_usd'], trade_size)

            if swap.token_in:
                stats['unique_tokens'].add(swap.token_in)
            if swap.token_out:
                stats['unique_tokens'].add(swap.token_out)
            stats['unique_dexes'].add(swap.dex)

        for addr, stats in wallet_stats.items():
            stats['address'] = addr
            stats['unique_tokens'] = len(stats['unique_tokens'])
            stats['unique_dexes'] = len(stats['unique_dexes'])
            if stats['swap_count'] > 0:
                stats['average_trade_size_usd'] = stats['total_volume_usd'] / stats['swap_count']
            else:
                stats['average_trade_size_usd'] = 0.0
        return wallet_stats
