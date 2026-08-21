#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel}")

# 1) config.py (نسخه کامل با تنظیمات جدید)
write("src/core/config.py", """
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from enum import Enum

class Mode(str, Enum):
    research = "research"
    paper = "paper"
    live = "live"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    mode: Mode = Mode.research
    live_trading_enabled: bool = False
    database_url: str = "sqlite:///data/whale.db"
    eth_enabled: bool = True
    bsc_enabled: bool = False
    solana_enabled: bool = False
    eth_primary_provider: str = "alchemy"
    eth_backup_provider: str = "etherscan"
    eth_rpc_url: Optional[str] = None
    eth_ws_url: Optional[str] = None
    eth_etherscan_api_key: Optional[str] = None
    eth_etherscan_base_url: str = "https://api.etherscan.io/api"
    eth_chain_id: int = 1
    eth_confirmation_blocks: int = 6
    eth_finality_blocks: int = 20
    eth_request_timeout: int = 30
    eth_max_retries: int = 5
    eth_rate_limit: int = 5
    eth_backfill_batch_size: int = 100
    eth_backfill_resume_file: str = "data/backfill_resume.json"
    bsc_primary_provider: str = "quicknode"
    bsc_backup_provider: str = "bscscan"
    bsc_rpc_url: Optional[str] = None
    bsc_ws_url: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    bsc_chain_id: int = 56
    solana_primary_provider: str = "helius"
    solana_backup_provider: str = "solscan"
    solana_rpc_url: Optional[str] = None
    solana_ws_url: Optional[str] = None
    solana_api_key: Optional[str] = None
    whale_min_total_volume_usd: float = 1_000_000
    whale_min_avg_trade_usd: float = 50_000
    whale_min_largest_trade_usd: float = 100_000
    whale_min_buy_volume_usd: float = 500_000
    whale_min_swap_count: int = 10
    whale_lookback_days: int = 30
    whale_score_threshold_candidate: float = 60
    whale_score_threshold_whale: float = 80
    whale_volume_weight: float = 0.25
    whale_avg_trade_weight: float = 0.20
    whale_largest_trade_weight: float = 0.20
    whale_activity_weight: float = 0.15
    whale_dex_activity_weight: float = 0.10
    whale_capital_weight: float = 0.10
    weight_capital: float = 0.15
    weight_volume: float = 0.15
    weight_tx_size: float = 0.15
    weight_consistency: float = 0.10
    weight_roi: float = 0.15
    weight_win_rate: float = 0.15
    weight_entry_timing: float = 0.15
    min_liquidity_usd: float = 1_000_000
    min_24h_volume_usd: float = 500_000
    min_market_cap_usd: float = 5_000_000
    min_token_age_days: int = 7
    max_token_age_days: int = 3650
    min_whale_activity_count: int = 3
    consensus_window_minutes: int = 60
    min_independent_whales: int = 3
    min_net_flow_usd: float = 500_000
    signal_min_score: float = 85
    signal_min_confidence: float = 80
    required_confirmations: int = 6
    rate_limit_enabled: bool = True
    cost_tracking_enabled: bool = True
    gate_api_key: Optional[str] = None
    gate_api_secret: Optional[str] = None
    buy_confidence_threshold: float = 80
    sell_confidence_threshold: float = 80
    native_asset_symbol: str = "ETH"
    wrapped_native_symbol: str = "WETH"
    wrapped_native_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    stablecoin_addresses_ethereum: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7,0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F"
    dex_swap_topic_uniswap_v2: str = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

settings = Settings()
""")

# 2) models.py (فقط Wallet و جداول فعالیت)
write("src/storage/models.py", """
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    first_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    last_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    balance_usd = Column(Float, default=0.0)
    portfolio_value_usd = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    whale_score = Column(Float, nullable=True)
    smart_money_score = Column(Float, nullable=True)
    predictive_wallet_score = Column(Float, nullable=True)
    status = Column(String, default="active")
    extra_data = Column(JSON, nullable=True)
    total_volume_usd = Column(Float, default=0.0)
    buy_volume_usd = Column(Float, default=0.0)
    sell_volume_usd = Column(Float, default=0.0)
    net_flow_usd = Column(Float, default=0.0)
    swap_count = Column(Integer, default=0)
    buy_count = Column(Integer, default=0)
    sell_count = Column(Integer, default=0)
    average_trade_size_usd = Column(Float, default=0.0)
    largest_trade_size_usd = Column(Float, default=0.0)
    unique_tokens = Column(Integer, default=0)
    unique_dexes = Column(Integer, default=0)
    active_days = Column(Integer, default=0)
    address_type = Column(String, default="unknown")
    exclusion_reason = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint('chain', 'address', name='uq_wallets_chain_address'),
        Index('ix_wallets_chain_whale_score', 'chain', 'whale_score'),
        Index('ix_wallets_chain_last_seen', 'chain', 'last_seen'),
        Index('ix_wallets_chain_total_volume', 'chain', 'total_volume_usd'),
        Index('ix_wallets_chain_status', 'chain', 'status'),
    )

class WalletActivity(Base):
    __tablename__ = "wallet_activity"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    window = Column(String, nullable=False)
    buy_volume = Column(Float, default=0.0)
    sell_volume = Column(Float, default=0.0)
    net_flow = Column(Float, default=0.0)
    swap_count = Column(Integer, default=0)
    average_trade = Column(Float, default=0.0)
    largest_trade = Column(Float, default=0.0)

class WalletTokenActivity(Base):
    __tablename__ = "wallet_token_activity"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    token_address = Column(String, nullable=False)
    token_symbol = Column(String, nullable=True)
    buy_volume = Column(Float, default=0.0)
    sell_volume = Column(Float, default=0.0)
    buy_count = Column(Integer, default=0)
    sell_count = Column(Integer, default=0)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint('wallet_id', 'token_address', name='uq_wallet_token'),
    )
""")

# 3) repositories.py (فقط Wallet و Activity)
write("src/storage/repositories.py", """
from typing import Optional
from sqlalchemy.orm import Session
from src.storage.models import Wallet, WalletActivity, WalletTokenActivity

class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

class WalletRepository(BaseRepository):
    def get_by_address(self, chain: str, address: str) -> Optional[Wallet]:
        return self.session.query(Wallet).filter_by(chain=chain, address=address).first()
    def add(self, wallet: Wallet):
        self.session.add(wallet)

class WalletActivityRepository(BaseRepository):
    def add(self, activity: WalletActivity):
        self.session.add(activity)

class WalletTokenActivityRepository(BaseRepository):
    def add(self, activity: WalletTokenActivity):
        self.session.add(activity)
""")

# 4) whale_scorer.py
write("src/scoring/whale_scorer.py", """
import math
from typing import Dict, Any, List
from src.core.config import settings

def log_normalize(value: float, min_val: float = 1.0, max_val: float = 1e12) -> float:
    if value <= 0:
        return 0.0
    value = max(min_val, min(value, max_val))
    log_min = math.log10(min_val)
    log_max = math.log10(max_val)
    log_val = math.log10(value)
    normalized = (log_val - log_min) / (log_max - log_min)
    return max(0.0, min(100.0, normalized * 100.0))

def percentile_normalize(value: float, all_values: List[float]) -> float:
    if not all_values:
        return 0.0
    count = len(all_values)
    rank = sum(1 for x in all_values if x <= value)
    percentile = (rank / count) * 100.0
    return max(0.0, min(100.0, percentile))

def compute_whale_score(stats: Dict[str, Any]) -> float:
    w_volume = settings.whale_volume_weight
    w_avg = settings.whale_avg_trade_weight
    w_largest = settings.whale_largest_trade_weight
    w_activity = settings.whale_activity_weight
    w_dex = settings.whale_dex_activity_weight
    w_capital = settings.whale_capital_weight

    vol_score = log_normalize(stats.get('total_volume_usd', 0), 1, 1e12)
    avg_score = log_normalize(stats.get('average_trade_size_usd', 0), 1, 1e9)
    largest_score = log_normalize(stats.get('largest_trade_size_usd', 0), 1, 1e9)
    activity_score = log_normalize(stats.get('swap_count', 0), 1, 100000)
    dex_score = log_normalize(stats.get('unique_dexes', 0), 1, 50)
    capital_score = log_normalize(stats.get('balance_usd', 0), 1, 1e12)

    score = (
        w_volume * vol_score +
        w_avg * avg_score +
        w_largest * largest_score +
        w_activity * activity_score +
        w_dex * dex_score +
        w_capital * capital_score
    )
    return max(0.0, min(100.0, score))
""")

# 5) excluded_addresses.py
write("src/detection/excluded_addresses.py", """
from typing import Dict, Set

class ExcludedAddressRegistry:
    def __init__(self):
        self._excluded: Dict[str, Set[str]] = {}
        self._load_defaults()

    def _load_defaults(self):
        self.add_address("0x0000000000000000000000000000000000000000", "burn", "burn", "official")

    def add_address(self, address: str, category: str, reason: str, source: str):
        addr = address.lower()
        if category not in self._excluded:
            self._excluded[category] = set()
        self._excluded[category].add(addr)

    def is_excluded(self, address: str) -> bool:
        addr = address.lower()
        for addrs in self._excluded.values():
            if addr in addrs:
                return True
        return False

    def get_category(self, address: str) -> str:
        addr = address.lower()
        for category, addrs in self._excluded.items():
            if addr in addrs:
                return category
        return None
""")

# 6) wallet_discovery.py
write("src/detection/wallet_discovery.py", """
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
""")

# 7) whale_detector.py
write("src/detection/whale_detector.py", """
from typing import Dict, Any
from src.core.config import settings
from src.scoring.whale_scorer import compute_whale_score
from src.detection.excluded_addresses import ExcludedAddressRegistry

class WhaleDetector:
    def __init__(self, registry: ExcludedAddressRegistry):
        self.registry = registry

    def is_candidate(self, stats: Dict[str, Any]) -> bool:
        if stats['total_volume_usd'] >= settings.whale_min_total_volume_usd: return True
        if stats['average_trade_size_usd'] >= settings.whale_min_avg_trade_usd: return True
        if stats['largest_trade_size_usd'] >= settings.whale_min_largest_trade_usd: return True
        if stats['buy_volume_usd'] >= settings.whale_min_buy_volume_usd: return True
        if stats['swap_count'] >= settings.whale_min_swap_count: return True
        return False

    def is_excluded(self, address: str) -> bool:
        return self.registry.is_excluded(address)

    def detect_whale(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        address = stats['address']
        if self.is_excluded(address):
            return {'is_whale': False, 'is_candidate': False, 'status': 'EXCLUDED',
                    'whale_score': None, 'exclusion_reason': self.registry.get_category(address)}

        if not self.is_candidate(stats):
            return {'is_whale': False, 'is_candidate': False,
                    'status': 'ACTIVE' if stats['swap_count'] > 0 else 'UNKNOWN',
                    'whale_score': compute_whale_score(stats), 'exclusion_reason': None}

        whale_score = compute_whale_score(stats)
        if whale_score >= settings.whale_score_threshold_whale:
            return {'is_whale': True, 'is_candidate': True, 'status': 'WHALE',
                    'whale_score': whale_score, 'exclusion_reason': None}
        elif whale_score >= settings.whale_score_threshold_candidate:
            return {'is_whale': False, 'is_candidate': True, 'status': 'WHALE_CANDIDATE',
                    'whale_score': whale_score, 'exclusion_reason': None}
        else:
            return {'is_whale': False, 'is_candidate': True, 'status': 'ACTIVE',
                    'whale_score': whale_score, 'exclusion_reason': None}
""")

# 8) wallet_profile.py
write("src/detection/wallet_profile.py", """
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator
from src.detection.whale_detector import WhaleDetector

class WalletProfileBuilder:
    def __init__(self, swaps: List[NormalizedSwap], excluded_registry, as_of: Optional[datetime] = None):
        self.aggregator = WalletAggregator(swaps, as_of)
        self.detector = WhaleDetector(excluded_registry)

    def build_profiles(self) -> Dict[str, Dict[str, Any]]:
        stats = self.aggregator.aggregate()
        profiles = {}
        for addr, wallet_stats in stats.items():
            detection = self.detector.detect_whale(wallet_stats)
            profiles[addr] = {**wallet_stats,
                              'whale_score': detection['whale_score'],
                              'status': detection['status'],
                              'is_whale': detection['is_whale'],
                              'is_candidate': detection['is_candidate'],
                              'exclusion_reason': detection['exclusion_reason']}
        return profiles
""")

# 9) tests (5 تست ساده)
write("tests/unit/detection/test_whale_score.py", """
from src.scoring.whale_scorer import compute_whale_score
def test_score():
    stats = {'total_volume_usd': 10_000_000, 'average_trade_size_usd': 500_000,
             'largest_trade_size_usd': 2_000_000, 'swap_count': 100,
             'unique_dexes': 5, 'balance_usd': 5_000_000}
    score = compute_whale_score(stats)
    assert 0 <= score <= 100
""")

write("tests/unit/detection/test_excluded.py", """
from src.detection.excluded_addresses import ExcludedAddressRegistry
def test_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xabc", "CEX", "Binance", "official")
    assert reg.is_excluded("0xabc")
""")

write("tests/unit/detection/test_whale_detector.py", """
from src.detection.whale_detector import WhaleDetector
from src.detection.excluded_addresses import ExcludedAddressRegistry
def test_candidate():
    reg = ExcludedAddressRegistry()
    detector = WhaleDetector(reg)
    stats = {'total_volume_usd': 2_000_000, 'average_trade_size_usd': 50_000,
             'largest_trade_size_usd': 100_000, 'buy_volume_usd': 1_500_000,
             'swap_count': 10, 'unique_dexes': 1, 'balance_usd': 0}
    assert detector.is_candidate(stats) == True
""")

write("tests/unit/detection/test_wallet_discovery.py", """
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_discovery():
    swaps = [
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                       timestamp=datetime(2024,1,1,tzinfo=UTC), log_index=0, wallet_address="0xw1",
                       token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95),
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                       timestamp=datetime(2024,1,2,tzinfo=UTC), log_index=0, wallet_address="0xw2",
                       token_in="0xtoken", token_out="0xusdc", side="SELL", usd_value=800, confidence=95),
    ]
    agg = WalletAggregator(swaps)
    stats = agg.aggregate()
    assert len(stats) == 2
""")

write("tests/unit/detection/test_no_lookahead.py", """
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_no_lookahead():
    t1 = datetime(2024,1,1,tzinfo=UTC)
    t2 = datetime(2024,1,2,tzinfo=UTC)
    swap1 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                           timestamp=t1, log_index=0, wallet_address="0xw",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95)
    swap2 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                           timestamp=t2, log_index=0, wallet_address="0xw",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=999000, confidence=95)
    agg_t1 = WalletAggregator([swap1, swap2], as_of=t1)
    stats_t1 = agg_t1.aggregate()["0xw"]
    assert stats_t1['total_volume_usd'] == 1000
""")

# اجرای تست‌ها و commit
print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "feat: add wallet discovery and whale detection (Phase 6)"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Phase 6 complete.")
