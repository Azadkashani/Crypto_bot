#!/usr/bin/env python3
"""
Phase 6 - Wallet Discovery & Whale Detection
Creates all necessary files and runs tests.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

def write_file(relative_path: str, content: str):
    path = PROJECT_ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    print(f"✅ نوشته شد: {relative_path}")

# --------------------------------------------------------------------
# 1. config.py
# --------------------------------------------------------------------
write_file('src/core/config.py', r'''
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from enum import Enum

class Mode(str, Enum):
    research = "research"
    paper = "paper"
    live = "live"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Project
    mode: Mode = Mode.research
    live_trading_enabled: bool = False

    # Database
    database_url: str = "sqlite:///data/whale.db"

    # Chain flags
    eth_enabled: bool = True
    bsc_enabled: bool = False
    solana_enabled: bool = False

    # Ethereum
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

    # BSC
    bsc_primary_provider: str = "quicknode"
    bsc_backup_provider: str = "bscscan"
    bsc_rpc_url: Optional[str] = None
    bsc_ws_url: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    bsc_chain_id: int = 56

    # Solana
    solana_primary_provider: str = "helius"
    solana_backup_provider: str = "solscan"
    solana_rpc_url: Optional[str] = None
    solana_ws_url: Optional[str] = None
    solana_api_key: Optional[str] = None

    # Whale Detection (Phase 6)
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

    # Scoring Weights (for Smart Money later, kept for future)
    weight_capital: float = 0.15
    weight_volume: float = 0.15
    weight_tx_size: float = 0.15
    weight_consistency: float = 0.10
    weight_roi: float = 0.15
    weight_win_rate: float = 0.15
    weight_entry_timing: float = 0.15

    # Token Universe Filters (not used yet)
    min_liquidity_usd: float = 1_000_000
    min_24h_volume_usd: float = 500_000
    min_market_cap_usd: float = 5_000_000
    min_token_age_days: int = 7
    max_token_age_days: int = 3650
    min_whale_activity_count: int = 3

    # Consensus (not used yet)
    consensus_window_minutes: int = 60
    min_independent_whales: int = 3
    min_net_flow_usd: float = 500_000

    # Signal (not used yet)
    signal_min_score: float = 85
    signal_min_confidence: float = 80

    # Finality
    required_confirmations: int = 6

    # Rate Limit & Cost Tracking
    rate_limit_enabled: bool = True
    cost_tracking_enabled: bool = True

    # Gate.io (not used yet)
    gate_api_key: Optional[str] = None
    gate_api_secret: Optional[str] = None

    # DEX / Swap Classification (Phase 5)
    buy_confidence_threshold: float = 80
    sell_confidence_threshold: float = 80
    native_asset_symbol: str = "ETH"
    wrapped_native_symbol: str = "WETH"
    wrapped_native_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    stablecoin_addresses_ethereum: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7,0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F"
    dex_swap_topic_uniswap_v2: str = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

settings = Settings()
'''.strip() + '\n')

# --------------------------------------------------------------------
# 2. models.py (full content)
# --------------------------------------------------------------------
write_file('src/storage/models.py', r'''
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

    # New fields for whale detection
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
        Index('ix_wallets_chain_address', 'chain', 'address'),
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

    __table_args__ = (
        Index('ix_wallet_activity_wallet_time', 'wallet_id', 'timestamp'),
        Index('ix_wallet_activity_wallet_window', 'wallet_id', 'window'),
    )

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
        Index('ix_wallet_token_wallet', 'wallet_id'),
        Index('ix_wallet_token_token', 'token_address'),
    )

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False, unique=True)
    transaction_index = Column(Integer)
    from_address = Column(String)
    to_address = Column(String)
    value = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String)
    classification = Column(String)
    confidence = Column(Float)
    log_index = Column(Integer, default=0)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_transactions_chain_timestamp', 'chain', 'timestamp'),
        Index('ix_transactions_chain_address_timestamp', 'chain', 'from_address', 'timestamp'),
        Index('ix_transactions_hash', 'transaction_hash'),
    )

class WhaleEvent(Base):
    __tablename__ = "whale_events"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    wallet = Column(String, nullable=False)
    token = Column(String, nullable=False)
    side = Column(String, nullable=False)
    usd_value = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    transaction_hash = Column(String)
    dex = Column(String)
    whale_score = Column(Float)
    smart_money_score = Column(Float)
    predictive_wallet_score = Column(Float)
    confidence = Column(Float)
    regime = Column(String)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_whale_events_chain_token_timestamp', 'chain', 'token', 'timestamp'),
        Index('ix_whale_events_wallet_timestamp', 'wallet', 'timestamp'),
    )

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    signal_score = Column(Float)
    confidence = Column(Float)
    components = Column(JSON)
    mode = Column(String)
    gate_available = Column(Boolean)
    regime = Column(String)
    status = Column(String)

    __table_args__ = (
        Index('ix_signals_chain_token_timestamp', 'chain', 'token', 'timestamp'),
    )

class WalletPerformance(Base):
    __tablename__ = "wallet_performance"
    id = Column(Integer, primary_key=True)
    wallet = Column(String, nullable=False)
    token = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    entry_price = Column(Float)
    entry_usd = Column(Float)
    regime = Column(String)
    return_1m = Column(Float, nullable=True)
    return_5m = Column(Float, nullable=True)
    return_15m = Column(Float, nullable=True)
    return_30m = Column(Float, nullable=True)
    return_1h = Column(Float, nullable=True)
    return_4h = Column(Float, nullable=True)
    return_24h = Column(Float, nullable=True)
    mfe = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    win = Column(Boolean, nullable=True)

    __table_args__ = (
        Index('ix_wallet_perf_wallet_timestamp', 'wallet', 'timestamp'),
    )

class ExcludedAddress(Base):
    __tablename__ = "excluded_addresses"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    label = Column(String)
    reason = Column(String)
    source = Column(String)

    __table_args__ = (
        Index('ix_excluded_addresses_chain_address', 'chain', 'address'),
    )

class TokenStats(Base):
    __tablename__ = "token_stats"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    market_cap = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    gate_available = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))

class WhaleConsensus(Base):
    __tablename__ = "whale_consensus"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    window_start = Column(DateTime, nullable=False)
    total_buy_volume = Column(Float, default=0.0)
    total_sell_volume = Column(Float, default=0.0)
    net_flow = Column(Float, default=0.0)
    independent_whales = Column(Integer, default=0)
    consensus_score = Column(Float, default=0.0)

    __table_args__ = (
        Index('ix_consensus_chain_token_window', 'chain', 'token', 'window_start'),
    )

class Block(Base):
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String, nullable=False, unique=True)
    parent_hash = Column(String)
    timestamp = Column(DateTime, nullable=False)
    transaction_count = Column(Integer, default=0)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_blocks_chain_number', 'chain', 'block_number'),
        Index('ix_blocks_chain_timestamp', 'chain', 'timestamp'),
    )

class TokenTransfer(Base):
    __tablename__ = "token_transfers"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False)
    log_index = Column(Integer, nullable=False)
    token_address = Column(String, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount_raw = Column(String, nullable=False)
    amount_normalized = Column(Float, nullable=True)
    decimals = Column(Integer, nullable=True)
    token_symbol = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_token_transfers_chain_token', 'chain', 'token_address', 'timestamp'),
        Index('ix_token_transfers_chain_tx', 'chain', 'transaction_hash'),
        Index('ix_token_transfers_chain_from', 'chain', 'from_address', 'timestamp'),
        Index('ix_token_transfers_chain_to', 'chain', 'to_address', 'timestamp'),
    )

class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False)
    transaction_index = Column(Integer)
    log_index = Column(Integer, nullable=False)
    contract_address = Column(String, nullable=False)
    topic0 = Column(String, nullable=False)
    topics = Column(JSON, nullable=True)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_event_logs_chain_contract', 'chain', 'contract_address', 'timestamp'),
        Index('ix_event_logs_chain_tx', 'chain', 'transaction_hash'),
        Index('ix_event_logs_chain_timestamp', 'chain', 'timestamp'),
    )

class Swap(Base):
    __tablename__ = "swaps"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    dex = Column(String, nullable=False)
    protocol_version = Column(String, nullable=True)
    tx_hash = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    log_index = Column(Integer, nullable=False)
    wallet_address = Column(String, nullable=False)
    token_in = Column(String, nullable=False)
    token_out = Column(String, nullable=False)
    amount_in_raw = Column(String, nullable=True)
    amount_out_raw = Column(String, nullable=True)
    amount_in = Column(Float, nullable=True)
    amount_out = Column(Float, nullable=True)
    token_in_decimals = Column(Integer, nullable=True)
    token_out_decimals = Column(Integer, nullable=True)
    token_in_symbol = Column(String, nullable=True)
    token_out_symbol = Column(String, nullable=True)
    side = Column(String, nullable=False)
    native_value = Column(Float, nullable=True)
    usd_value = Column(Float, nullable=True)
    pool_address = Column(String, nullable=True)
    router_address = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    classification_reason = Column(String, nullable=True)
    swap_group_id = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint('chain', 'tx_hash', 'log_index', name='uq_swap_chain_tx_log'),
        Index('ix_swaps_chain_tx', 'chain', 'tx_hash'),
        Index('ix_swaps_chain_wallet_timestamp', 'chain', 'wallet_address', 'timestamp'),
        Index('ix_swaps_chain_token_in_timestamp', 'chain', 'token_in', 'timestamp'),
        Index('ix_swaps_chain_token_out_timestamp', 'chain', 'token_out', 'timestamp'),
        Index('ix_swaps_chain_dex_timestamp', 'chain', 'dex', 'timestamp'),
        Index('ix_swaps_side_timestamp', 'side', 'timestamp'),
    )
'''.strip() + '\n')

# --------------------------------------------------------------------
# 3. repositories.py
# --------------------------------------------------------------------
write_file('src/storage/repositories.py', r'''
from typing import List, Optional
from sqlalchemy.orm import Session
from src.storage.models import (
    Wallet, Transaction, WhaleEvent, Signal, ExcludedAddress, TokenStats,
    WhaleConsensus, Block, TokenTransfer, EventLog, Swap,
    WalletActivity, WalletTokenActivity
)

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

class TransactionRepository(BaseRepository):
    def get_by_hash(self, tx_hash: str) -> Optional[Transaction]:
        return self.session.query(Transaction).filter_by(transaction_hash=tx_hash).first()

    def add(self, tx: Transaction):
        self.session.add(tx)

class WhaleEventRepository(BaseRepository):
    def add(self, event: WhaleEvent):
        self.session.add(event)

class SignalRepository(BaseRepository):
    def add(self, signal: Signal):
        self.session.add(signal)

class ExcludedAddressRepository(BaseRepository):
    def get_by_address(self, chain: str, address: str) -> Optional[ExcludedAddress]:
        return self.session.query(ExcludedAddress).filter_by(chain=chain, address=address).first()

    def add(self, excluded: ExcludedAddress):
        self.session.add(excluded)

class TokenStatsRepository(BaseRepository):
    def get_by_token(self, chain: str, token: str) -> Optional[TokenStats]:
        return self.session.query(TokenStats).filter_by(chain=chain, token=token).first()

    def add(self, stats: TokenStats):
        self.session.add(stats)

class WhaleConsensusRepository(BaseRepository):
    def add(self, consensus: WhaleConsensus):
        self.session.add(consensus)

class BlockRepository(BaseRepository):
    def get_by_hash(self, block_hash: str) -> Optional[Block]:
        return self.session.query(Block).filter_by(block_hash=block_hash).first()

    def get_by_number(self, chain: str, block_number: int) -> Optional[Block]:
        return self.session.query(Block).filter_by(chain=chain, block_number=block_number).first()

    def add(self, block: Block):
        self.session.add(block)

class TokenTransferRepository(BaseRepository):
    def get_by_tx_log(self, tx_hash: str, log_index: int) -> Optional[TokenTransfer]:
        return self.session.query(TokenTransfer).filter_by(transaction_hash=tx_hash, log_index=log_index).first()

    def add(self, transfer: TokenTransfer):
        self.session.add(transfer)

class EventLogRepository(BaseRepository):
    def get_by_tx_log(self, tx_hash: str, log_index: int) -> Optional[EventLog]:
        return self.session.query(EventLog).filter_by(transaction_hash=tx_hash, log_index=log_index).first()

    def add(self, log: EventLog):
        self.session.add(log)

class SwapRepository(BaseRepository):
    def get_by_tx_log(self, chain: str, tx_hash: str, log_index: int) -> Optional[Swap]:
        return self.session.query(Swap).filter_by(chain=chain, tx_hash=tx_hash, log_index=log_index).first()

    def add(self, swap: Swap):
        self.session.add(swap)

    def get_all_valid_swaps(self, chain: str) -> List[Swap]:
        return self.session.query(Swap).filter(Swap.chain == chain, Swap.side.in_(['BUY', 'SELL'])).all()
'''.strip() + '\n')

# --------------------------------------------------------------------
# 4. scoring/whale_scorer.py
# --------------------------------------------------------------------
write_file('src/scoring/whale_scorer.py', r'''
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
'''.strip() + '\n')

# --------------------------------------------------------------------
# 5. detection/excluded_addresses.py
# --------------------------------------------------------------------
write_file('src/detection/excluded_addresses.py', r'''
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
'''.strip() + '\n')

# --------------------------------------------------------------------
# 6. detection/wallet_discovery.py
# --------------------------------------------------------------------
write_file('src/detection/wallet_discovery.py', r'''
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set
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
            'chain': 'ethereum',
            'address': '',
            'first_seen': None,
            'last_seen': None,
            'total_volume_usd': 0.0,
            'buy_volume_usd': 0.0,
            'sell_volume_usd': 0.0,
            'net_flow_usd': 0.0,
            'swap_count': 0,
            'buy_count': 0,
            'sell_count': 0,
            'largest_trade_size_usd': 0.0,
            'unique_tokens': set(),
            'unique_dexes': set(),
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
'''.strip() + '\n')

# --------------------------------------------------------------------
# 7. detection/whale_detector.py
# --------------------------------------------------------------------
write_file('src/detection/whale_detector.py', r'''
from typing import Dict, Any
from src.core.config import settings
from src.scoring.whale_scorer import compute_whale_score
from src.detection.excluded_addresses import ExcludedAddressRegistry

class WhaleDetector:
    def __init__(self, registry: ExcludedAddressRegistry):
        self.registry = registry

    def is_candidate(self, stats: Dict[str, Any]) -> bool:
        if stats['total_volume_usd'] >= settings.whale_min_total_volume_usd:
            return True
        if stats['average_trade_size_usd'] >= settings.whale_min_avg_trade_usd:
            return True
        if stats['largest_trade_size_usd'] >= settings.whale_min_largest_trade_usd:
            return True
        if stats['buy_volume_usd'] >= settings.whale_min_buy_volume_usd:
            return True
        if stats['swap_count'] >= settings.whale_min_swap_count:
            return True
        return False

    def is_excluded(self, address: str) -> bool:
        return self.registry.is_excluded(address)

    def detect_whale(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        address = stats['address']
        if self.is_excluded(address):
            return {
                'is_whale': False,
                'is_candidate': False,
                'status': 'EXCLUDED',
                'whale_score': None,
                'exclusion_reason': self.registry.get_category(address),
            }

        if not self.is_candidate(stats):
            return {
                'is_whale': False,
                'is_candidate': False,
                'status': 'ACTIVE' if stats['swap_count'] > 0 else 'UNKNOWN',
                'whale_score': compute_whale_score(stats),
                'exclusion_reason': None,
            }

        whale_score = compute_whale_score(stats)
        if whale_score >= settings.whale_score_threshold_whale:
            return {
                'is_whale': True,
                'is_candidate': True,
                'status': 'WHALE',
                'whale_score': whale_score,
                'exclusion_reason': None,
            }
        elif whale_score >= settings.whale_score_threshold_candidate:
            return {
                'is_whale': False,
                'is_candidate': True,
                'status': 'WHALE_CANDIDATE',
                'whale_score': whale_score,
                'exclusion_reason': None,
            }
        else:
            return {
                'is_whale': False,
                'is_candidate': True,
                'status': 'ACTIVE',
                'whale_score': whale_score,
                'exclusion_reason': None,
            }
'''.strip() + '\n')

# --------------------------------------------------------------------
# 8. detection/wallet_profile.py
# --------------------------------------------------------------------
write_file('src/detection/wallet_profile.py', r'''
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator
from src.detection.whale_detector import WhaleDetector

class WalletProfileBuilder:
    def __init__(self, swaps: List[NormalizedSwap], excluded_registry, as_of: Optional[datetime] = None):
        self.aggregator = WalletAggregator(swaps, as_of)
        self.excluded_registry = excluded_registry
        self.detector = WhaleDetector(excluded_registry)

    def build_profiles(self) -> Dict[str, Dict[str, Any]]:
        stats = self.aggregator.aggregate()
        profiles = {}
        for addr, wallet_stats in stats.items():
            detection = self.detector.detect_whale(wallet_stats)
            profile = {
                **wallet_stats,
                'whale_score': detection['whale_score'],
                'status': detection['status'],
                'is_whale': detection['is_whale'],
                'is_candidate': detection['is_candidate'],
                'exclusion_reason': detection['exclusion_reason'],
            }
            profiles[addr] = profile
        return profiles
'''.strip() + '\n')

# --------------------------------------------------------------------
# 9. Test files
# --------------------------------------------------------------------
tests_dir = 'tests/unit/detection'
write_file(f'{tests_dir}/test_wallet_discovery.py', r'''
import pytest
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def make_swap(wallet, side, usd_value, timestamp):
    return NormalizedSwap(
        chain="ethereum", dex="uniswap_v2", tx_hash=f"0x{hash(wallet)}",
        block_number=1, timestamp=timestamp, log_index=0,
        wallet_address=wallet, token_in="0xtokenA", token_out="0xtokenB",
        side=side, usd_value=usd_value, confidence=90,
    )

def test_wallet_discovery_unique():
    swaps = [
        make_swap("0xwallet1", "BUY", 1000, datetime(2024,1,1,tzinfo=UTC)),
        make_swap("0xwallet2", "SELL", 500, datetime(2024,1,2,tzinfo=UTC)),
        make_swap("0xwallet1", "BUY", 2000, datetime(2024,1,3,tzinfo=UTC)),
    ]
    agg = WalletAggregator(swaps)
    stats = agg.aggregate()
    assert len(stats) == 2
    assert "0xwallet1" in stats
    assert "0xwallet2" in stats
'''.strip() + '\n')

write_file(f'{tests_dir}/test_wallet_aggregation.py', r'''
import pytest
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_aggregate_basic():
    swaps = [
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                       timestamp=datetime(2024,1,1,tzinfo=UTC), log_index=0, wallet_address="0xwallet",
                       token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95),
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                       timestamp=datetime(2024,1,2,tzinfo=UTC), log_index=0, wallet_address="0xwallet",
                       token_in="0xtoken", token_out="0xusdc", side="SELL", usd_value=800, confidence=95),
    ]
    agg = WalletAggregator(swaps)
    stats = agg.aggregate()["0xwallet"]
    assert stats['swap_count'] == 2
    assert stats['buy_volume_usd'] == 1000
    assert stats['sell_volume_usd'] == 800
    assert stats['net_flow_usd'] == 200
    assert stats['average_trade_size_usd'] == 900
    assert stats['largest_trade_size_usd'] == 1000
    assert stats['unique_tokens'] == 2
    assert stats['unique_dexes'] == 1
'''.strip() + '\n')

write_file(f'{tests_dir}/test_excluded_addresses.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry

def test_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xabc", "CEX", "Binance", "official")
    assert reg.is_excluded("0xabc")
    assert reg.get_category("0xabc") == "CEX"
    assert not reg.is_excluded("0xdef")
'''.strip() + '\n')

write_file(f'{tests_dir}/test_whale_thresholds.py', r'''
import pytest
from src.detection.whale_detector import WhaleDetector
from src.detection.excluded_addresses import ExcludedAddressRegistry

def test_candidate_detection():
    reg = ExcludedAddressRegistry()
    detector = WhaleDetector(reg)
    stats = {'total_volume_usd': 2_000_000, 'average_trade_size_usd': 50_000,
             'largest_trade_size_usd': 100_000, 'buy_volume_usd': 1_500_000,
             'swap_count': 10, 'unique_dexes': 1, 'balance_usd': 0}
    assert detector.is_candidate(stats) == True
'''.strip() + '\n')

write_file(f'{tests_dir}/test_whale_score.py', r'''
from src.scoring.whale_scorer import compute_whale_score

def test_whale_score_basic():
    stats = {'total_volume_usd': 10_000_000, 'average_trade_size_usd': 500_000,
             'largest_trade_size_usd': 2_000_000, 'swap_count': 100,
             'unique_dexes': 5, 'balance_usd': 5_000_000}
    score = compute_whale_score(stats)
    assert 0 <= score <= 100
    assert score > 50
'''.strip() + '\n')

write_file(f'{tests_dir}/test_score_normalization.py', r'''
from src.scoring.whale_scorer import log_normalize

def test_log_normalize():
    assert log_normalize(0) == 0.0
    assert log_normalize(1) == 0.0
    assert log_normalize(1e12) == 100.0
    assert 0 < log_normalize(1000) < 100
    assert log_normalize(1000) > log_normalize(100)
'''.strip() + '\n')

write_file(f'{tests_dir}/test_wallet_profile.py', r'''
import pytest
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_profile import WalletProfileBuilder
from src.detection.excluded_addresses import ExcludedAddressRegistry

def test_build_profile():
    reg = ExcludedAddressRegistry()
    swaps = [
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                       timestamp=datetime(2024,1,1,tzinfo=UTC), log_index=0, wallet_address="0xwallet",
                       token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=100000, confidence=95),
        NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                       timestamp=datetime(2024,1,2,tzinfo=UTC), log_index=0, wallet_address="0xwallet",
                       token_in="0xtoken", token_out="0xusdc", side="SELL", usd_value=80000, confidence=95),
    ]
    builder = WalletProfileBuilder(swaps, reg)
    profiles = builder.build_profiles()
    assert "0xwallet" in profiles
    profile = profiles["0xwallet"]
    assert profile['swap_count'] == 2
    assert profile['status'] in ['ACTIVE', 'WHALE_CANDIDATE', 'WHALE']
    assert 'whale_score' in profile
'''.strip() + '\n')

write_file(f'{tests_dir}/test_contract_exclusion.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry
from src.detection.whale_detector import WhaleDetector

def test_contract_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xcontract", "CONTRACT", "Smart contract", "official")
    detector = WhaleDetector(reg)
    stats = {'address': '0xcontract', 'total_volume_usd': 1000000, 'average_trade_size_usd': 100000,
             'largest_trade_size_usd': 500000, 'buy_volume_usd': 800000, 'swap_count': 20,
             'unique_dexes': 1, 'balance_usd': 0}
    result = detector.detect_whale(stats)
    assert result['status'] == 'EXCLUDED'
    assert result['is_whale'] == False
'''.strip() + '\n')

write_file(f'{tests_dir}/test_cex_exclusion.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry
from src.detection.whale_detector import WhaleDetector

def test_cex_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xcex", "CEX", "Exchange", "official")
    detector = WhaleDetector(reg)
    stats = {'address': '0xcex', 'total_volume_usd': 1000000, 'average_trade_size_usd': 100000,
             'largest_trade_size_usd': 500000, 'buy_volume_usd': 800000, 'swap_count': 20,
             'unique_dexes': 1, 'balance_usd': 0}
    result = detector.detect_whale(stats)
    assert result['status'] == 'EXCLUDED'
'''.strip() + '\n')

write_file(f'{tests_dir}/test_dex_exclusion.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry
from src.detection.whale_detector import WhaleDetector

def test_dex_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xdexrouter", "DEX_ROUTER", "Uniswap router", "official")
    detector = WhaleDetector(reg)
    stats = {'address': '0xdexrouter', 'total_volume_usd': 1000000, 'average_trade_size_usd': 100000,
             'largest_trade_size_usd': 500000, 'buy_volume_usd': 800000, 'swap_count': 20,
             'unique_dexes': 1, 'balance_usd': 0}
    result = detector.detect_whale(stats)
    assert result['status'] == 'EXCLUDED'
'''.strip() + '\n')

write_file(f'{tests_dir}/test_bridge_exclusion.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry
from src.detection.whale_detector import WhaleDetector

def test_bridge_excluded():
    reg = ExcludedAddressRegistry()
    reg.add_address("0xbridge", "BRIDGE", "Bridge contract", "official")
    detector = WhaleDetector(reg)
    stats = {'address': '0xbridge', 'total_volume_usd': 1000000, 'average_trade_size_usd': 100000,
             'largest_trade_size_usd': 500000, 'buy_volume_usd': 800000, 'swap_count': 20,
             'unique_dexes': 1, 'balance_usd': 0}
    result = detector.detect_whale(stats)
    assert result['status'] == 'EXCLUDED'
'''.strip() + '\n')

write_file(f'{tests_dir}/test_large_transfer_not_whale.py', r'''
import pytest
from src.detection.excluded_addresses import ExcludedAddressRegistry
from src.detection.whale_detector import WhaleDetector

def test_large_transfer_not_whale():
    reg = ExcludedAddressRegistry()
    detector = WhaleDetector(reg)
    stats = {'address': '0xwallet', 'total_volume_usd': 0, 'average_trade_size_usd': 0,
             'largest_trade_size_usd': 0, 'buy_volume_usd': 0, 'swap_count': 0,
             'unique_dexes': 0, 'balance_usd': 0}
    result = detector.detect_whale(stats)
    assert result['is_whale'] == False
    assert result['status'] not in ['WHALE', 'WHALE_CANDIDATE']
'''.strip() + '\n')

write_file(f'{tests_dir}/test_no_lookahead_wallet_score.py', r'''
import pytest
from datetime import datetime, UTC
from src.dex.models import NormalizedSwap
from src.detection.wallet_discovery import WalletAggregator

def test_no_lookahead():
    t1 = datetime(2024,1,1,tzinfo=UTC)
    t2 = datetime(2024,1,2,tzinfo=UTC)
    swap1 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x1", block_number=1,
                           timestamp=t1, log_index=0, wallet_address="0xwallet",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=1000, confidence=95)
    swap2 = NormalizedSwap(chain="ethereum", dex="uniswap_v2", tx_hash="0x2", block_number=2,
                           timestamp=t2, log_index=0, wallet_address="0xwallet",
                           token_in="0xusdc", token_out="0xtoken", side="BUY", usd_value=999000, confidence=95)
    agg_t1 = WalletAggregator([swap1, swap2], as_of=t1)
    stats_t1 = agg_t1.aggregate()["0xwallet"]
    assert stats_t1['total_volume_usd'] == 1000
    assert stats_t1['swap_count'] == 1

    agg_t2 = WalletAggregator([swap1, swap2], as_of=t2)
    stats_t2 = agg_t2.aggregate()["0xwallet"]
    assert stats_t2['total_volume_usd'] == 1000000
    assert stats_t2['swap_count'] == 2
'''.strip() + '\n')

write_file(f'{tests_dir}/test_wallet_database.py', r'''
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.storage.models import Base, Wallet
from src.storage.repositories import WalletRepository

def test_wallet_crud():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repo = WalletRepository(session)
    wallet = Wallet(address="0xwallet", chain="ethereum", total_volume_usd=1000, whale_score=70)
    repo.add(wallet)
    session.commit()
    fetched = repo.get_by_address("ethereum", "0xwallet")
    assert fetched is not None
    assert fetched.total_volume_usd == 1000
    session.close()
'''.strip() + '\n')

# --------------------------------------------------------------------
# 10. docs/phase6.md
# --------------------------------------------------------------------
write_file('docs/phase6.md', r'''
# Phase 6: Wallet Discovery & Whale Detection

## Overview
This phase identifies trader wallets from validated DEX swaps, aggregates their activity, filters out excluded addresses (exchanges, routers, bridges, etc.), and computes an initial whale score based on size and activity metrics. It does not evaluate smart money performance yet.

## Key Components
- `src/detection/wallet_discovery.py`: Aggregates swaps per wallet.
- `src/detection/whale_detector.py`: Determines candidate and whale status.
- `src/detection/excluded_addresses.py`: Registry for excluded addresses.
- `src/scoring/whale_scorer.py`: Log-normalized scoring.
- `src/storage/models.py`: Wallet and activity tables.

## Whale Score Formula
